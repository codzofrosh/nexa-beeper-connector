import time

class Metrics:
    processed = 0
    dropped = 0

    @classmethod
    def snapshot(cls, queue_depth):
        return {
            "processed": cls.processed,
            "dropped": cls.dropped,
            "queue_depth": queue_depth,
        }
