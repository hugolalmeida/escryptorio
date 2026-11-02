CREATE TABLE arena_experiments (
    id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE arena_results (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL UNIQUE REFERENCES arena_experiments(id),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TRIGGER arena_experiments_no_update BEFORE UPDATE ON arena_experiments BEGIN SELECT RAISE(ABORT, 'immutable arena experiment'); END;
CREATE TRIGGER arena_experiments_no_delete BEFORE DELETE ON arena_experiments BEGIN SELECT RAISE(ABORT, 'immutable arena experiment'); END;
CREATE TRIGGER arena_results_no_update BEFORE UPDATE ON arena_results BEGIN SELECT RAISE(ABORT, 'immutable arena result'); END;
CREATE TRIGGER arena_results_no_delete BEFORE DELETE ON arena_results BEGIN SELECT RAISE(ABORT, 'immutable arena result'); END;
