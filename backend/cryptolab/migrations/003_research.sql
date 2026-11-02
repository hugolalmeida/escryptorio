CREATE TABLE research_protocols (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE research_runs (
    id TEXT PRIMARY KEY,
    protocol_id TEXT NOT NULL REFERENCES research_protocols(id),
    partition TEXT NOT NULL CHECK (partition IN ('train','validation','test')),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX research_protocol_runs ON research_runs(protocol_id,partition);
CREATE TRIGGER research_protocols_no_update BEFORE UPDATE ON research_protocols BEGIN SELECT RAISE(ABORT, 'immutable protocol'); END;
CREATE TRIGGER research_protocols_no_delete BEFORE DELETE ON research_protocols BEGIN SELECT RAISE(ABORT, 'immutable protocol'); END;
CREATE TRIGGER research_runs_no_update BEFORE UPDATE ON research_runs BEGIN SELECT RAISE(ABORT, 'immutable result'); END;
CREATE TRIGGER research_runs_no_delete BEFORE DELETE ON research_runs BEGIN SELECT RAISE(ABORT, 'immutable result'); END;
