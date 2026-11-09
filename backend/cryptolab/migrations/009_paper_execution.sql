CREATE TABLE paper_mark_evidence (
 id TEXT PRIMARY KEY, wallet_id TEXT NOT NULL REFERENCES paper_wallets(id),
 binding_id TEXT NOT NULL REFERENCES paper_bindings(id), signal_id TEXT NOT NULL REFERENCES monitor_signals(id),
 event_id TEXT NOT NULL UNIQUE REFERENCES paper_events(event_id), source_time_ms INTEGER NOT NULL,
 idempotency_key TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(wallet_id,source_time_ms), UNIQUE(wallet_id,idempotency_key)
);
CREATE TABLE paper_execution_evidence (
 id TEXT PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE REFERENCES paper_decisions(id),
 wallet_id TEXT NOT NULL REFERENCES paper_wallets(id), binding_id TEXT NOT NULL REFERENCES paper_bindings(id),
 signal_id TEXT NOT NULL REFERENCES monitor_signals(id), candle_time INTEGER NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('BUY','SELL')), idempotency_key TEXT NOT NULL,
 event_id TEXT NOT NULL UNIQUE REFERENCES paper_events(event_id), payload TEXT NOT NULL,
 UNIQUE(wallet_id,candle_time,action), UNIQUE(wallet_id,idempotency_key)
);
CREATE TRIGGER paper_mark_evidence_no_update BEFORE UPDATE ON paper_mark_evidence BEGIN SELECT RAISE(ABORT,'immutable mark evidence'); END;
CREATE TRIGGER paper_mark_evidence_no_delete BEFORE DELETE ON paper_mark_evidence BEGIN SELECT RAISE(ABORT,'immutable mark evidence'); END;
CREATE TRIGGER paper_execution_evidence_no_update BEFORE UPDATE ON paper_execution_evidence BEGIN SELECT RAISE(ABORT,'immutable execution evidence'); END;
CREATE TRIGGER paper_execution_evidence_no_delete BEFORE DELETE ON paper_execution_evidence BEGIN SELECT RAISE(ABORT,'immutable execution evidence'); END;
