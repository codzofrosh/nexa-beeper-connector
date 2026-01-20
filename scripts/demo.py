"""
Demo script to insert sample actions into the database.
"""
from bridge.db.database import get_db
import time

db = get_db()
now = int(time.time())

db.execute("""
INSERT OR IGNORE INTO actions
(message_id, platform, room_id, label, action, confidence, state, created_at)
VALUES
('demo-1','whatsapp','r1','ENQUIRY','NOTIFY',0.91,'DONE',?),
('demo-2','whatsapp','r2','COMPLAINT','ESCALATE',0.88,'DONE',?)
""", (now, now))

db.commit()
