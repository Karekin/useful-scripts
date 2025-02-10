-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS riskcontrol;


-- Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS cep_rules (
  id VARCHAR(255) PRIMARY KEY,
  version INTEGER,
  parameters TEXT,
  function TEXT,
  pattern TEXT,
  libs TEXT,
  binding_keys TEXT,
  rule_type VARCHAR(50)
);
