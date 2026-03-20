-- MySQL Init Script
-- Runs once when the container first starts

CREATE DATABASE IF NOT EXISTS seo_automation
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE seo_automation;

-- Grant privileges (user is already created via env vars, this ensures full access)
GRANT ALL PRIVILEGES ON seo_automation.* TO 'seo_user'@'%';
FLUSH PRIVILEGES;
