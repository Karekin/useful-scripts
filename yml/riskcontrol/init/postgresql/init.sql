-- 如果数据库不存在则创建（虽然环境变量已指定，但保留可确保）
CREATE DATABASE IF NOT EXISTS riskcontrol;

-- 切换到目标数据库
\c riskcontrol

-- 创建表（添加IF NOT EXISTS防止重复创建）
CREATE TABLE IF NOT EXISTS public.cep_rules (
  id VARCHAR(255) PRIMARY KEY,
  version INTEGER,
  parameters TEXT,
  function TEXT,
  pattern TEXT,
  libs TEXT,
  binding_keys TEXT,
  rule_type VARCHAR(50)
  );
