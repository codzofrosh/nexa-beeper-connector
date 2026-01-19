def migrate(db):
    print("🔄 Applying sidecar migrations")
    # cols = { row["name"] for row in db.execute("PRAGMA table_info(actions)").fetchall() }
    cols = {row[1] for row in db.execute("PRAGMA table_info(actions)")}
    for data in cols:
        print("   -", data)

    if "claimed_at" not in cols:
        db.execute("ALTER TABLE actions ADD COLUMN claimed_at INTEGER")

    if "executor_id" not in cols:
        db.execute("ALTER TABLE actions ADD COLUMN executor_id TEXT")

    if "executed_at" not in cols:
        db.execute("ALTER TABLE actions ADD COLUMN executed_at INTEGER")

    if "external_id" not in cols:
        db.execute("ALTER TABLE actions ADD COLUMN external_id TEXT")

    db.commit()
