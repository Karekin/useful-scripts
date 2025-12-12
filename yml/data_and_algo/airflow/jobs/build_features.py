# jobs/build_features.py
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

def run_build_features(execution_date: str):
    spark = (
        SparkSession.builder
        .appName("store-replenishment-build-features")
        .getOrCreate()
    )

    spark.sql("USE demo_catalog.amoro_db")

    # 1）从原始表读取
    src = spark.table("demo_catalog.amoro_db.order_wide")

    # 2）做特征聚合（这里只示例，替换成你 notebook 里的逻辑）
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

    (
        feature_df
        .writeTo(target_table)
        .option("fanout-enabled", "true")
        .createOrReplace()   # 首次建表；增量可以改成 append()
    )

    print("build_features done:", feature_df.count())
