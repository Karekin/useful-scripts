# jobs/batch_predict.py
import os
import mlflow
from pyspark.sql import SparkSession, functions as F

FEATURE_TABLE = "demo_catalog.amoro_db.store_item_features_scoring"
TARGET_TABLE  = "demo_catalog.amoro_db.store_item_scores"
MODEL_URI     = "models:/store_replenishment_rf/Production"  # 或固定 runs:/<run_id>/model

def run_batch_predict(execution_date: str):
    spark = SparkSession.builder.appName("store-replenishment-predict").getOrCreate()
    spark.sql("USE demo_catalog.amoro_db")

    mlflow.set_tracking_uri("http://mlflow:5000")
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"
    os.environ["AWS_ACCESS_KEY_ID"] = "admin"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "password"
    os.environ["AWS_REGION"] = "us-east-1"

    # 1) 读 scoring 特征
    feature_df = spark.table(FEATURE_TABLE)

    # 2) 加载 MLflow 模型为 Spark UDF
    predict_udf = mlflow.pyfunc.spark_udf(spark, model_uri=MODEL_URI)

    scored = (
        feature_df
        .withColumn("score", predict_udf(F.struct(*feature_df.columns)))
        .withColumn("predict_time", F.current_timestamp())
        .withColumn("model_name", F.lit("store_replenishment_rf"))
        .withColumn("model_version", F.lit("Production"))
    )

    (
        scored
        .select(
            "store_id", "item_id", "ds",
            "score", "predict_time", "model_name", "model_version"
        )
        .writeTo(TARGET_TABLE)
        .append()
    )

    print("batch_predict done, rows =", scored.count())
