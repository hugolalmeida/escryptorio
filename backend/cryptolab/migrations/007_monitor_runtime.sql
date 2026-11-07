CREATE TABLE monitor_runtime (
    config_hash TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    definition TEXT NOT NULL,
    last_candle INTEGER,
    last_evaluation_ms INTEGER,
    state TEXT NOT NULL,
    error_code TEXT,
    lease_owner TEXT,
    lease_until_ms INTEGER
);
CREATE INDEX monitor_runtime_bot ON monitor_runtime(bot_id);
CREATE TABLE monitor_leases (
    scope_hash TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    until_ms INTEGER NOT NULL
);
