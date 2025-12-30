import os

AI_SIDECAR_HOST = os.getenv("AI_SIDECAR_HOST", "0.0.0.0")
AI_SIDECAR_PORT = int(os.getenv("AI_SIDECAR_PORT", "8080"))
