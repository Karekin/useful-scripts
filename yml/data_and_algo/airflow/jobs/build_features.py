import argparse
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

def run_build_features(execution_date: str):
    print(f"Running build_features for date: {execution_date}")
    spark = (
        SparkSession.builder
        .appName("store-replenishment-build-features")
        .getOrCreate()
    )

    spark.sql("USE demo_catalog.amoro_db")

    # 1）从原始表读取
    try:
        # 确保数据库存在
        spark.sql("CREATE DATABASE IF NOT EXISTS demo_catalog.amoro_db")
        # 尝试读取，如果不存在则创建假数据供测试
        src = spark.table("demo_catalog.amoro_db.order_wide")
    except Exception as e:
        print(f"Source table not found ({e}), creating dummy data for testing...")
        src = spark.createDataFrame([
            ("store_1", "item_a", "2025-01-01", 10, 100.0),
            ("store_1", "item_b", "2025-01-01", 5, 50.0),
            ("store_2", "item_a", "2025-01-01", 8, 80.0)
        ], ["store_id", "item_id", "ds", "qty", "amount"])

    # 2）做特征聚合
    feature_df = (
        src
        .groupBy("store_id", "item_id", "ds")
        .agg(
            F.sum("qty").alias("sales"),
            F.sum("amount").alias("gmv"),
        )
    )

    # 3）写入 Iceberg 特征表
    target_table = "demo_catalog.amoro_db.store_item_features"

    try:
        (
            feature_df
            .writeTo(target_table)
            .option("fanout-enabled", "true")
            .createOrReplace()
        )
        print("build_features done:", feature_df.count())
    except Exception as e:
        print(f"Error writing to table: {e}")
    
    spark.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Execution date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    run_build_features(args.date)
