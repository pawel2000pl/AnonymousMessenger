-- WARNING: TIMESTAMPS AS MILLISECONDS
-- CHANGE ACCESS DATA BEFORE EXECUTE ON THE REMOTE SERVER

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
    last_login_timestamp BIGINT NOT NULL DEFAULT 0,
  	CHECK(LENGTH(login) < 256 AND LENGTH(login) > 1)
);

CREATE UNIQUE INDEX accounts_logins ON accounts (login(16));
CREATE INDEX accounts_login_timestamp ON accounts (last_login_timestamp);

CREATE TABLE tokens (
    hash VARCHAR(64) PRIMARY KEY,
    account BIGINT,
    created_timestamp BIGINT DEFAULT 0,
    last_activity_timestamp BIGINT DEFAULT 0,
    no_activity_lifespan BIGINT DEFAULT 3600000,
    max_lifespan BIGINT DEFAULT 604800000,
    FOREIGN KEY (account) REFERENCES accounts (id)
);

CREATE INDEX tokens_accounts ON tokens (account);
CREATE INDEX tokens_timestamps ON tokens (created_timestamp, last_activity_timestamp);

CREATE VIEW valid_tokens AS 
    SELECT 
        * 
    FROM 
        tokens 
    WHERE 
        created_timestamp > UNIX_TIMESTAMP() * 1000 - max_lifespan 
    AND 
        last_activity_timestamp > UNIX_TIMESTAMP() * 1000 - no_activity_lifespan;

CREATE VIEW account_tokens AS 
    SELECT 
        * 
    FROM 
        accounts 
    JOIN 
        valid_tokens ON (valid_tokens.account = accounts.id);

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
    can_create TINYINT NOT NULL DEFAULT 1,
    last_read_time BIGINT NOT NULL DEFAULT 0,
    FOREIGN KEY (thread) REFERENCES threads (id),
    FOREIGN KEY (account) REFERENCES accounts (id)
);

CREATE UNIQUE INDEX users_names ON users (thread, username(64));
CREATE UNIQUE INDEX users_hash ON users (hash);
CREATE INDEX users_account ON users (account);

CREATE TABLE push_notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user BIGINT,
    hash VARCHAR(64),
    subscription_information LONGBLOB,
    vapid_private_key LONGBLOB,
    last_delivered_message_timestamp BIGINT NOT NULL DEFAULT 0,
    FOREIGN KEY (user) REFERENCES users (id)
);

CREATE INDEX push_notifications_user ON push_notifications (user);

CREATE TABLE messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user BIGINT,
    timestamp BIGINT NOT NULL DEFAULT 0,
    content LONGBLOB,
    is_system TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (user) REFERENCES users (id),
    CHECK(content IS NOT NULL AND LENGTH(content) > 0 AND LENGTH(content) < 262144)
);

CREATE UNIQUE INDEX messages_index ON messages (user, timestamp);

CREATE VIEW messages_view AS
    SELECT 
        init_user.id AS init_user_id,
        messages.id AS id,
        CASE messages.is_system WHEN 1 THEN "SYSTEM" ELSE users.username END AS sender,
        users.hash = init_user.hash AND NOT messages.is_system AS me,
        messages.timestamp AS timestamp,
        messages.content AS content,
        messages.is_system AS is_system
    FROM 
        users AS init_user
    JOIN
        threads ON (init_user.thread = threads.id)
    JOIN 
        users ON (users.thread = threads.id)
    JOIN
        messages ON (messages.user = users.id);

CREATE TABLE errors (
    timestamp BIGINT,
    readable_timestamp TEXT AS (FROM_UNIXTIME(timestamp/1000)) VIRTUAL,
    message LONGTEXT
);

CREATE INDEX errors_timestamp ON errors(timestamp);

CREATE VIEW short_errors AS
    SELECT 
        readable_timestamp, 
        LEFT(message, IFNULL(NULLIF(LOCATE("\n", message), 0), 64)-1) AS short_message
    FROM
        errors
    ORDER BY
        timestamp;

CREATE TABLE statistic_hist (
    duration INTEGER,
    ident varchar(16),
    `count` BIGINT DEFAULT 0
);

CREATE UNIQUE INDEX statistic_hist_index ON statistic_hist (duration, ident);

CREATE VIEW agregated_statistics AS
    SELECT 
        ident,
        COUNT(*) * AVG(duration) AS total,
        COUNT(*) AS exec_count,
        AVG(duration) AS aver,
        MIN(duration) AS minimum,
        MAX(duration) AS maximum,
        STD(duration) AS std
    FROM
        statistic_hist
    GROUP BY
        ident
    ORDER BY
        total DESC, 
        ident ASC;
