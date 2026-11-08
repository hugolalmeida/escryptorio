CREATE TABLE paper_bindings (
 id TEXT PRIMARY KEY, wallet_id TEXT NOT NULL REFERENCES paper_wallets(id), bot_id TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0), config_hash TEXT NOT NULL REFERENCES monitor_runtime(config_hash),
 payload TEXT NOT NULL, UNIQUE(wallet_id, version)
);
CREATE TABLE paper_binding_events (
 binding_id TEXT NOT NULL REFERENCES paper_bindings(id), sequence INTEGER NOT NULL CHECK(sequence > 0),
 kind TEXT NOT NULL CHECK(kind IN ('REGISTERED','ACTIVE','DISABLED')), payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, PRIMARY KEY(binding_id, sequence)
);
CREATE TABLE paper_binding_heads (
 binding_id TEXT PRIMARY KEY REFERENCES paper_bindings(id), sequence INTEGER NOT NULL CHECK(sequence > 0),
 event_hash TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('REGISTERED','ACTIVE','DISABLED'))
);
CREATE TABLE paper_binding_active (
 wallet_id TEXT PRIMARY KEY REFERENCES paper_wallets(id), bot_id TEXT NOT NULL UNIQUE,
 binding_id TEXT NOT NULL UNIQUE REFERENCES paper_bindings(id)
);
CREATE TABLE paper_decisions (
 id TEXT PRIMARY KEY, wallet_id TEXT NOT NULL REFERENCES paper_wallets(id),
 binding_id TEXT NOT NULL REFERENCES paper_bindings(id), signal_id TEXT NOT NULL REFERENCES monitor_signals(id),
 config_hash TEXT NOT NULL REFERENCES monitor_runtime(config_hash), candle_time INTEGER NOT NULL,
 payload TEXT NOT NULL, UNIQUE(wallet_id,candle_time)
);
CREATE TABLE paper_decision_events (
 decision_id TEXT NOT NULL REFERENCES paper_decisions(id), sequence INTEGER NOT NULL CHECK(sequence > 0),
 kind TEXT NOT NULL CHECK(kind IN ('RECORDED','INVALIDATED','EXPIRED')), payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, PRIMARY KEY(decision_id,sequence)
);
CREATE TABLE paper_decision_heads (
 decision_id TEXT PRIMARY KEY REFERENCES paper_decisions(id), sequence INTEGER NOT NULL CHECK(sequence > 0),
 event_hash TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('RECORDED','INVALIDATED','EXPIRED'))
);
CREATE TABLE paper_decision_clock (id INTEGER PRIMARY KEY CHECK(id=1), high_water_ms INTEGER NOT NULL);
INSERT INTO paper_decision_clock VALUES (1,0);
CREATE TRIGGER paper_bindings_no_update BEFORE UPDATE ON paper_bindings BEGIN SELECT RAISE(ABORT,'immutable binding'); END;
CREATE TRIGGER paper_bindings_no_delete BEFORE DELETE ON paper_bindings BEGIN SELECT RAISE(ABORT,'immutable binding'); END;
CREATE TRIGGER paper_binding_events_no_update BEFORE UPDATE ON paper_binding_events BEGIN SELECT RAISE(ABORT,'immutable binding event'); END;
CREATE TRIGGER paper_binding_events_no_delete BEFORE DELETE ON paper_binding_events BEGIN SELECT RAISE(ABORT,'immutable binding event'); END;
CREATE TRIGGER paper_binding_heads_no_delete BEFORE DELETE ON paper_binding_heads BEGIN SELECT RAISE(ABORT,'binding checkpoint required'); END;
CREATE TRIGGER paper_decisions_no_update BEFORE UPDATE ON paper_decisions BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
CREATE TRIGGER paper_decisions_no_delete BEFORE DELETE ON paper_decisions BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
CREATE TRIGGER paper_decision_events_no_update BEFORE UPDATE ON paper_decision_events BEGIN SELECT RAISE(ABORT,'immutable decision event'); END;
CREATE TRIGGER paper_decision_events_no_delete BEFORE DELETE ON paper_decision_events BEGIN SELECT RAISE(ABORT,'immutable decision event'); END;
CREATE TRIGGER paper_decision_heads_no_delete BEFORE DELETE ON paper_decision_heads BEGIN SELECT RAISE(ABORT,'decision checkpoint required'); END;
CREATE TRIGGER paper_decision_clock_no_delete BEFORE DELETE ON paper_decision_clock BEGIN SELECT RAISE(ABORT,'clock checkpoint required'); END;
CREATE TRIGGER paper_decision_clock_no_rewind BEFORE UPDATE ON paper_decision_clock WHEN NEW.high_water_ms < OLD.high_water_ms BEGIN SELECT RAISE(ABORT,'clock rewind'); END;
