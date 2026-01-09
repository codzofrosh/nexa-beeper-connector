"""In-memory de-duplication helper used by the worker.

This module implements a tiny TTL-based deduplicator that remembers
recent message IDs so transient replays are ignored.
"""

import time

class Deduplicator:
    """Simple TTL-based deduplicator.

    `seen_before` returns True if the message id has been seen within `ttl` seconds.
    """
    def __init__(self, ttl=300):
        self.seen = {}
        self.ttl = ttl

    def seen_before(self, message_id: str) -> bool:
        """Return True if the message ID was observed recently."""
        now = time.time()
        self.seen = {
            k: v for k, v in self.seen.items()
            if now - v < self.ttl
        }
        if message_id in self.seen:
            return True
        self.seen[message_id] = now
        return False
