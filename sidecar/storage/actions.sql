CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- identity
    message_id TEXT NOT NULL,
    platform   TEXT NOT NULL,
    room_id    TEXT NOT NULL,

    -- decision
    label      TEXT NOT NULL,
    action     TEXT NOT NULL,
    confidence REAL NOT NULL,

    -- lifecycle
    state TEXT NOT NULL CHECK (
        state IN ('PENDING', 'EXECUTING', 'DONE', 'FAILED')
    ),

    -- timestamps
    created_at INTEGER NOT NULL,
    claimed_at INTEGER,
    executed_at INTEGER,

    -- executor metadata
    executor_id TEXT,

    -- hard guarantee
    UNIQUE(message_id, action)
);
