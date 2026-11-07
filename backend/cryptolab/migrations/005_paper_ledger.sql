CREATE TABLE paper_wallets (
    id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL UNIQUE,
    creation_key TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    payload_hash TEXT NOT NULL
);
CREATE TABLE paper_heads (
    wallet_id TEXT PRIMARY KEY REFERENCES paper_wallets(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    event_hash TEXT NOT NULL
);
CREATE TABLE paper_events (
    wallet_id TEXT NOT NULL REFERENCES paper_wallets(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    event_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('genesis','state','fill','mark')),
    payload TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    PRIMARY KEY (wallet_id,sequence),
    UNIQUE (wallet_id,idempotency_key)
);
CREATE TRIGGER paper_wallets_no_update BEFORE UPDATE ON paper_wallets BEGIN SELECT RAISE(ABORT, 'immutable paper wallet'); END;
CREATE TRIGGER paper_wallets_no_delete BEFORE DELETE ON paper_wallets BEGIN SELECT RAISE(ABORT, 'immutable paper wallet'); END;
CREATE TRIGGER paper_events_no_update BEFORE UPDATE ON paper_events BEGIN SELECT RAISE(ABORT, 'immutable paper event'); END;
CREATE TRIGGER paper_events_no_delete BEFORE DELETE ON paper_events BEGIN SELECT RAISE(ABORT, 'immutable paper event'); END;
CREATE TRIGGER paper_heads_no_delete BEFORE DELETE ON paper_heads BEGIN SELECT RAISE(ABORT, 'paper checkpoint required'); END;
