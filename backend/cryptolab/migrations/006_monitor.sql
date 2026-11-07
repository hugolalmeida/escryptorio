CREATE TABLE monitor_signals (
    id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    candle_time INTEGER NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(bot_id,config_hash,candle_time)
);
CREATE INDEX monitor_signal_history ON monitor_signals(bot_id,config_hash,candle_time);
CREATE TRIGGER monitor_signals_no_update BEFORE UPDATE ON monitor_signals BEGIN SELECT RAISE(ABORT, 'immutable monitor signal'); END;
CREATE TRIGGER monitor_signals_no_delete BEFORE DELETE ON monitor_signals BEGIN SELECT RAISE(ABORT, 'immutable monitor signal'); END;
