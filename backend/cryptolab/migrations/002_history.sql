CREATE TABLE historical_jobs (
    id TEXT PRIMARY KEY,
    exchange TEXT NOT NULL DEFAULT 'Bybit' CHECK(exchange='Bybit'),
    market TEXT NOT NULL DEFAULT 'spot' CHECK(market='spot'),
    symbol TEXT NOT NULL CHECK(symbol IN ('BTCUSDT','ETHUSDT')),
    interval TEXT NOT NULL CHECK(interval IN ('15','60','240','D')),
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL CHECK(end_time > start_time),
    status TEXT NOT NULL CHECK(status IN ('queued','running','paused','failed','incomplete','completed')),
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    error_code TEXT,
    dataset_id TEXT,
    UNIQUE(exchange,market,symbol,interval,start_time,end_time)
);
CREATE INDEX historical_jobs_queue ON historical_jobs(status,created_at_ms);
CREATE TABLE historical_lease (
    id INTEGER PRIMARY KEY CHECK(id=1),
    owner TEXT NOT NULL,
    job_id TEXT NOT NULL REFERENCES historical_jobs(id),
    until_ms INTEGER NOT NULL
);
CREATE TABLE historical_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES historical_jobs(id),
    started_at_ms INTEGER NOT NULL,
    ended_at_ms INTEGER,
    status TEXT NOT NULL,
    collector_version TEXT NOT NULL,
    error_code TEXT
);
CREATE TABLE historical_candles (
    exchange TEXT NOT NULL CHECK(exchange='Bybit'),
    market TEXT NOT NULL CHECK(market='spot'),
    symbol TEXT NOT NULL CHECK(symbol IN ('BTCUSDT','ETHUSDT')),
    interval TEXT NOT NULL CHECK(interval IN ('15','60','240','D')),
    open_time INTEGER NOT NULL,
    payload TEXT NOT NULL,
    source_time_ms INTEGER NOT NULL,
    collected_at_ms INTEGER NOT NULL,
    run_id INTEGER NOT NULL REFERENCES historical_runs(id),
    PRIMARY KEY(exchange,market,symbol,interval,open_time)
) WITHOUT ROWID;
CREATE TABLE historical_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES historical_runs(id),
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    source_time_ms INTEGER NOT NULL,
    collected_at_ms INTEGER NOT NULL,
    received_count INTEGER NOT NULL,
    stored_count INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    open_count INTEGER NOT NULL,
    outside_count INTEGER NOT NULL
);
CREATE TABLE historical_gaps (
    job_id TEXT NOT NULL REFERENCES historical_jobs(id),
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    candle_count INTEGER NOT NULL,
    detected_at_ms INTEGER NOT NULL,
    PRIMARY KEY(job_id,start_time)
);
CREATE TABLE historical_datasets (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    candle_count INTEGER NOT NULL,
    approved_at_ms INTEGER NOT NULL,
    manifest TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX historical_dataset_catalog ON historical_datasets(symbol,interval,start_time,end_time);
CREATE TRIGGER historical_candles_no_update BEFORE UPDATE ON historical_candles
BEGIN
    SELECT RAISE(ABORT,'Historical candles are immutable');
END;
CREATE TRIGGER historical_candles_no_delete BEFORE DELETE ON historical_candles
BEGIN
    SELECT RAISE(ABORT,'Historical candles are immutable');
END;
CREATE TRIGGER historical_datasets_no_update BEFORE UPDATE ON historical_datasets
BEGIN
    SELECT RAISE(ABORT,'Approved datasets are immutable');
END;
CREATE TRIGGER historical_datasets_no_delete BEFORE DELETE ON historical_datasets
BEGIN
    SELECT RAISE(ABORT,'Approved datasets are immutable');
END;
