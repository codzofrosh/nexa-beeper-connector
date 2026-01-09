import os
import socket
import uuid

EXECUTOR_ID = os.getenv(
    "EXECUTOR_ID",
    f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
)
