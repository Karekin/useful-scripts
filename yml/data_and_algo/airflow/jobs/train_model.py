import argparse
import os
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from pyspark.sql import SparkSession

FEATURE_TABLE = "demo_catalog.amoro_db.store_item_features"
FEATURE_COLS = ["dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"]
TARGET_COL = "sales"

def run_train_model(execution_date: str):
    print(f"Running train_model for date: {execution_date}")
    spark = SparkSession.builder.appName("store-replenishment-train").getOrCreate()
    spark.sql("USE demo_catalog.amoro_db")

    try:
        pdf = spark.table(FEATURE_TABLE).toPandas()
        if pdf.empty:
            raise ValueError("Table is empty")
    except Exception as e:
        print(f"Error reading table {FEATURE_TABLE} or empty: {e}")
        print("Using dummy data for training...")
        pdf = pd.DataFrame({
            "store_id": ["s1"]*100,
            "item_id": ["i1"]*100,
            "ds": ["2025-01-01"]*100,
            "dayofweek": np.random.randint(0, 7, 100),
            "month": np.random.randint(1, 13, 100),
            "lag_1": np.random.rand(100) * 100,
            "lag_7": np.random.rand(100) * 100,
            "lag_14": np.random.rand(100) * 100,
            "rolling_7_mean": np.random.rand(100) * 100,
            "sales": np.random.rand(100) * 100
        })

    # 补齐列
    for col in FEATURE_COLS:
        if col not in pdf.columns:
            pdf[col] = 0.0
    if TARGET_COL not in pdf.columns:
        pdf[TARGET_COL] = 0.0

    X = pdf[FEATURE_COLS]
    y = pdf[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    mlflow.set_experiment("/store_replenishment")

    with mlflow.start_run() as run:
        model = RandomForestRegressor(n_estimators=10, max_depth=5, random_state=42) # 减少参数加快演示
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        mlflow.log_param("n_estimators", 10)
        mlflow.log_param("max_depth", 5)
        mlflow.log_metric("rmse", rmse)

        mlflow.sklearn.log_model(model, "model", input_example=X_train.iloc[:5])
        
        # 注册模型以便 batch_predict 使用
        model_uri = f"runs:/{run.info.run_id}/model"
        mlflow.register_model(model_uri, "store_replenishment_rf")

        print("train_model done, run_id =", run.info.run_id)
    
    spark.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Execution date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    run_train_model(args.date)
