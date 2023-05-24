-- WARNING: TIMESTAMPS AS MILLISECONDS
-- CHANGE ACCESS DATA BEFORE EXECUTE ON THE REMOTE SERVER

BEGIN;

CREATE DATABASE anonymous_messenger_db;
CREATE USER IF NOT EXISTS 'anonymous_messenger'@'localhost' IDENTIFIED BY 'anonymous_messenger_pass';
GRANT SELECT ON anonymous_messenger_db.* TO 'anonymous_messenger'@'localhost';
GRANT DELETE ON anonymous_messenger_db.* TO 'anonymous_messenger'@'localhost';
GRANT INSERT ON anonymous_messenger_db.* TO 'anonymous_messenger'@'localhost';
GRANT UPDATE ON anonymous_messenger_db.* TO 'anonymous_messenger'@'localhost';
GRANT CREATE TEMPORARY TABLES ON anonymous_messenger_db.* TO 'anonymous_messenger'@'localhost';
FLUSH PRIVILEGES;

USE anonymous_messenger_db;

CREATE TABLE accounts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    login TEXT, 
    password TEXT,
  	CHECK(LENGTH(login) < 256 AND LENGTH(login) > 1)
);

CREATE UNIQUE INDEX accounts_logins ON accounts (login(16));

CREATE TABLE tokens (
    hash VARCHAR(64) PRIMARY KEY,
    account BIGINT,
    created_timestamp BIGINT DEFAULT 0,
    last_activity_timestamp BIGINT DEFAULT 0,
    no_activity_lifespan BIGINT DEFAULT 3600,
    max_lifespan BIGINT DEFAULT 604800,
    FOREIGN KEY (account) REFERENCES accounts (id)
);

CREATE INDEX tokens_accounts ON tokens (account);
CREATE INDEX tokens_created ON tokens (created_timestamp);
CREATE INDEX tokens_activity ON tokens (last_activity_timestamp);

CREATE VIEW valid_tokens AS 
    SELECT * FROM tokens WHERE created_timestamp < UNIX_TIMESTAMP() * 1000 - max_lifespan AND last_activity_timestamp < UNIX_TIMESTAMP() * 1000 - no_activity_lifespan;

CREATE VIEW account_tokens AS 
    SELECT * FROM accounts JOIN valid_tokens ON (valid_tokens.account = accounts.id);

CREATE TABLE threads (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name TEXT
);

CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username TEXT CHECK(LENGTH(TRIM(username)) > 0 AND LENGTH(username) < 256),
    thread BIGINT,
    hash VARCHAR(64),
    closed TINYINT NOT NULL DEFAULT 0,
    account BIGINT DEFAULT NULL,
    FOREIGN KEY (thread) REFERENCES threads (id),
    FOREIGN KEY (account) REFERENCES accounts (id)
);

CREATE UNIQUE INDEX users_names ON users (thread, username(64));
CREATE UNIQUE INDEX users_hash ON users (hash);

CREATE TABLE messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY ,
    user BIGINT,
    timestamp BIGINT NOT NULL DEFAULT 0,
    content LONGTEXT,
    is_system TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (user) REFERENCES users (id),
    CHECK(content IS NOT NULL AND LENGTH(content) > 0 AND LENGTH(content) < 262144)
);

CREATE UNIQUE INDEX messages_index ON messages (user, timestamp);

COMMIT;