CREATE TABLE datasets (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL CHECK(symbol IN ('BTCUSDT','ETHUSDT')),
    interval TEXT NOT NULL CHECK(interval IN ('15','60','240','D')),
    created_at_ms INTEGER NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE snapshots (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (symbol, interval)
);
CREATE TABLE collection_status (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    last_attempt_ms INTEGER NOT NULL,
    last_success_ms INTEGER,
    error_code TEXT
);
