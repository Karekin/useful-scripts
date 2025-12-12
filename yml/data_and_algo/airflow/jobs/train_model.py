# jobs/train_model.py
import os
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from pyspark.sql import SparkSession

FEATURE_TABLE = "demo_catalog.amoro_db.store_item_features"
FEATURE_COLS = ["dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"]
TARGET_COL = "sales"

def run_train_model(execution_date: str):
    spark = SparkSession.builder.appName("store-replenishment-train").getOrCreate()
    spark.sql("USE demo_catalog.amoro_db")

    pdf = spark.table(FEATURE_TABLE).toPandas()
    X = pdf[FEATURE_COLS]
    y = pdf[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("/Users/445923692@qq.com/store_replenishment")

    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"
    os.environ["AWS_ACCESS_KEY_ID"] = "admin"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "password"
    os.environ["AWS_REGION"] = "us-east-1"

    with mlflow.start_run() as run:
        model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 8)
        mlflow.log_metric("rmse", rmse)

        mlflow.sklearn.log_model(model, "model", input_example=X_train.iloc[:5])

        print("train_model done, run_id =", run.info.run_id)
