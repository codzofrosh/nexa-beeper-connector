CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- business identity
    message_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    room_id TEXT NOT NULL,

    -- AI decision
    label TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,

    -- execution state machine
    state TEXT NOT NULL CHECK (
        state IN ('PENDING', 'EXECUTING', 'DONE', 'FAILED')
    ),

    -- executor coordination
    executor_id TEXT,
    claimed_at INTEGER,
    executed_at INTEGER,

    -- external system id (optional)
    external_id TEXT,

    -- ordering & replay
    created_at INTEGER NOT NULL,

    -- HARD GUARANTEE: AI can never create two actions for same message
    UNIQUE(message_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_actions_state_created
    ON actions(state, created_at);
