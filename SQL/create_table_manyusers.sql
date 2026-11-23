-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS userdata
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE userdata;

-- Drop table if exists (for clean re-creation)
DROP TABLE IF EXISTS manyusers;

-- Create manyusers table
CREATE TABLE manyusers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    address VARCHAR(255),
    work_phone VARCHAR(20),
    mobile_phone VARCHAR(20),
    company_name VARCHAR(255),
    title VARCHAR(255),
    department VARCHAR(100),
    source VARCHAR(50),
    type VARCHAR(50),
    user_descr TEXT,
    created_at DATETIME NOT NULL,
    
    INDEX idx_source (source),
    INDEX idx_type (type),
    INDEX idx_company (company_name),
    INDEX idx_created_at (created_at),
    INDEX idx_email (email),
    INDEX idx_username (username)
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Multi-franchise fictional character user database';
