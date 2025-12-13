from utils.common_job_utils import SparkJob
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

FEATURE_TABLE = "amoro_catalog.amoro_db.store_item_features"
FEATURE_COLS = ["dayofweek", "month", "lag_1", "lag_7", "lag_14", "rolling_7_mean"]
TARGET_COL = "sales"

if __name__ == "__main__":
    with SparkJob("train_model", enable_mlflow=True) as job:
        spark = job.spark
        # 使用 amoro_catalog.amoro_db（与 Amoro UI 中创建的 Catalog/Database 一致）
        spark.sql("USE amoro_catalog.amoro_db")

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

        # MLflow 上下文已由 SparkJob 初始化
        with mlflow.start_run() as run:
            model = RandomForestRegressor(n_estimators=10, max_depth=5, random_state=42)
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

            print(f"train_model done, run_id = {run.info.run_id}")
