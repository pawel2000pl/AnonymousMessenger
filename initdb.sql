-- TIMESTAMPS AS MILLISECONDS

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT,
    password TEXT
);

DROP INDEX IF EXISTS accounts_logins;
CREATE UNIQUE INDEX accounts_logins ON accounts (login);

CREATE TABLE IF NOT EXISTS tokens (
    hash TEXT PRIMARY KEY,
    account INTEGER,
    created_timestamp INTEGER DEFAULT 0,
    last_activity_timestamp INTEGER DEFAULT 0,
    no_activity_lifespan INTEGER DEFAULT 3600,
    max_lifespan INTEGER DEFAULT 604800,
    FOREIGN KEY (account) REFERENCES accounts (id)
);

DROP INDEX IF EXISTS tokens_accounts;
CREATE INDEX tokens_accounts ON tokens (account);

CREATE VIEW IF NOT EXISTS valid_tokens AS 
    SELECT *, CAST(STRFTIME('%s') AS INTEGER) * 1000 AS current_timestamp FROM tokens WHERE created_timestamp + max_lifespan < current_timestamp AND last_activity_timestamp + no_activity_lifespan < current_timestamp;

CREATE VIEW IF NOT EXISTS account_tokens AS 
    SELECT * FROM accounts JOIN valid_tokens ON (valid_tokens.account = accounts.id);


CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT CHECK(LENGTH(TRIM(username)) > 0 AND LENGTH(username) < 256),
    thread INTEGER,
    hash TEXT,
    closed INTEGER DEFAULT 0,
    account INTEGER DEFAULT NULL,
    FOREIGN KEY (thread) REFERENCES threads (id),
    FOREIGN KEY (account) REFERENCES accounts (id)
);

DROP INDEX IF EXISTS users_names;
CREATE UNIQUE INDEX users_names ON users (thread, username);
DROP INDEX IF EXISTS users_hash;
CREATE UNIQUE INDEX users_hash ON users (hash);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user INTEGER,
    timestamp INTEGER,
    content TEXT CHECK(LENGTH(content) > 0 AND LENGTH(content) < 262144),
    system INTEGER DEFAULT 0,
    FOREIGN KEY (user) REFERENCES users (id)
);

DROP INDEX IF EXISTS messages_index;
CREATE UNIQUE INDEX messages_index ON messages (user, timestamp);