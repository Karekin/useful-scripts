import argparse
import os
import mlflow
from pyspark.sql import SparkSession, functions as F

FEATURE_TABLE = "demo.demo_db2.store_item_features" # 复用
TARGET_TABLE  = "demo.demo_db2.store_item_scores"
MODEL_NAME    = "store_replenishment_rf"

def run_batch_predict(execution_date: str):
    print(f"Running batch_predict for date: {execution_date}")
    spark = SparkSession.builder.appName("store-replenishment-predict").getOrCreate()
    spark.sql("USE demo.demo_db2")

    try:
        # 0) 调试信息
        uri = os.environ.get('MLFLOW_TRACKING_URI', "http://mlflow:5000")
        print(f"DEBUG: MLFLOW_TRACKING_URI: {uri}")
        mlflow.set_tracking_uri(uri)

        # 1) 读数据
        try:
            feature_df = spark.table(FEATURE_TABLE)
            # 确保有特征列，没有就补0 (演示用)
            required_cols = ["dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"]
            for col in required_cols:
                if col not in feature_df.columns:
                    feature_df = feature_df.withColumn(col, F.lit(0.0))
        except:
             print(f"Table {FEATURE_TABLE} not found, using dummy data")
             feature_df = spark.createDataFrame([
                 ("s1", "i1", "2025-01-01", 1.0, 1.0, 10.0, 10.0, 10.0, 10.0)
             ], ["store_id", "item_id", "ds", "dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"])

        # 2) 加载 MLflow 模型
        # 动态获取最新 Production 或 None 版本的模型
        client = mlflow.tracking.MlflowClient()
        # 简单起见，直接用 latest version
        latest_versions = client.get_latest_versions(MODEL_NAME, stages=["None", "Staging", "Production"])
        if not latest_versions:
            print(f"No model found for {MODEL_NAME}")
            return

        latest_version = latest_versions[0].version
        model_uri = f"models:/{MODEL_NAME}/{latest_version}"
        print(f"Using model: {model_uri}")

        predict_udf = mlflow.pyfunc.spark_udf(spark, model_uri=model_uri)

        # 构造 struct 输入，必须和训练时的列顺序一致
        input_cols = ["dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"]

        scored = (
            feature_df
            .withColumn("score", predict_udf(F.struct(*[F.col(c) for c in input_cols])))
            .withColumn("predict_time", F.current_timestamp())
            .withColumn("model_name", F.lit(MODEL_NAME))
            .withColumn("model_version", F.lit(latest_version))
        )

        (
            scored
            .select(
                "store_id", "item_id", "ds",
                "score", "predict_time", "model_name", "model_version"
            )
            .writeTo(TARGET_TABLE)
            .createOrReplace() # 演示用 replace，生产用 append
        )
        print("batch_predict done, rows =", scored.count())

    except Exception as e:
        print(f"Error in batch_predict: {e}")
        import traceback
        traceback.print_exc()

    spark.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Execution date (YYYY-MM-DD)")
    args = parser.parse_args()

    run_batch_predict(args.date)
