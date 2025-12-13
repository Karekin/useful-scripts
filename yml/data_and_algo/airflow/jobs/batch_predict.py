from utils.common_job_utils import SparkJob
import mlflow
from pyspark.sql import functions as F

FEATURE_TABLE = "demo.demo_db2.store_item_features" # 复用
TARGET_TABLE  = "demo.demo_db2.store_item_scores"
MODEL_NAME    = "store_replenishment_rf"

if __name__ == "__main__":
    with SparkJob("batch_predict", enable_mlflow=True) as job:
        spark = job.spark
        spark.sql("USE demo.demo_db2")

        try:
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
            client = mlflow.tracking.MlflowClient()
            latest_versions = client.get_latest_versions(MODEL_NAME, stages=["None", "Staging", "Production"])
            if not latest_versions:
                print(f"No model found for {MODEL_NAME}")
            else:
                latest_version = latest_versions[0].version
                model_uri = f"models:/{MODEL_NAME}/{latest_version}"
                print(f"Using model: {model_uri}")

                predict_udf = mlflow.pyfunc.spark_udf(spark, model_uri=model_uri)

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
            raise e
