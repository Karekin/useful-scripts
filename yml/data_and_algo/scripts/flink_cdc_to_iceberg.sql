-- ============================================================
-- Flink CDC to Iceberg 示例
-- 
-- 前置条件：
-- 1. 在 Amoro UI 中已创建 Internal Catalog 'demo'
-- 2. MySQL 中有业务数据表
-- 
-- 使用方式：
-- 进入 Flink SQL Client：
--   docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh
-- ============================================================

-- 1. 创建 Iceberg Catalog（连接到 Amoro）
-- warehouse 参数为 Amoro 中的 Catalog 名称，不是 S3 路径
CREATE CATALOG amoro_catalog WITH (
  'type' = 'iceberg',
  'catalog-impl' = 'org.apache.iceberg.rest.RESTCatalog',
  'uri' = 'http://amoro:1630/api/iceberg/rest',
  'warehouse' = 'amoro_catalog'
);

-- 2. 创建 MySQL CDC Source（连接到业务数据库）
CREATE TABLE mysql_orders (
  order_id INT,
  customer_id INT,
  product_name STRING,
  quantity INT,
  order_date TIMESTAMP(3),
  PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
  'connector' = 'mysql-cdc',
  'hostname' = 'mysql',
  'port' = '3306',
  'username' = 'root',
  'password' = 'password',
  'database-name' = 'mydb',
  'table-name' = 'orders'
);

-- 3. 在 Iceberg 中创建目标表
USE CATALOG amoro_catalog;
CREATE DATABASE IF NOT EXISTS ods;

CREATE TABLE IF NOT EXISTS ods.orders (
  order_id INT,
  customer_id INT,
  product_name STRING,
  quantity INT,
  order_date TIMESTAMP(3),
  PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
  'format-version' = '2',
  'write.upsert.enabled' = 'true'
);

-- 4. 启动 CDC 同步作业
INSERT INTO amoro_catalog.ods.orders
SELECT * FROM default_catalog.default_database.mysql_orders;

-- ============================================================
-- 注意：
-- - 需要在 Flink lib 目录下有 flink-connector-mysql-cdc JAR
-- - 需要在 MySQL 中预先创建 orders 表和测试数据：
--
--   CREATE TABLE orders (
--     order_id INT PRIMARY KEY,
--     customer_id INT,
--     product_name VARCHAR(255),
--     quantity INT,
--     order_date DATETIME
--   );
--
--   INSERT INTO orders VALUES (1, 100, 'Product A', 2, NOW());
-- ============================================================

