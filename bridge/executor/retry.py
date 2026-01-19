MAX_ATTEMPTS = 5
BASE_DELAY = 2  # seconds

def can_retry(action) -> bool:
    return action["attempts"] < MAX_ATTEMPTS

def backoff_seconds(action) -> int:
    # exponential backoff with cap
    return min(BASE_DELAY * (2 ** action["attempts"]), 300)