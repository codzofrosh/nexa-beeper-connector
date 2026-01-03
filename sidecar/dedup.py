import time

class Deduplicator:
    def __init__(self, ttl=300):
        self.seen = {}
        self.ttl = ttl

    def seen_before(self, message_id: str) -> bool:
        now = time.time()
        self.seen = {
            k: v for k, v in self.seen.items()
            if now - v < self.ttl
        }
        if message_id in self.seen:
            return True
        self.seen[message_id] = now
        return False
