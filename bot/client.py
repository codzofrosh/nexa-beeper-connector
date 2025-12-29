import logging
from nio import AsyncClient

log = logging.getLogger("bot")


def create_client(homeserver: str, user_id: str, access_token: str) -> AsyncClient:
    client = AsyncClient(homeserver, user_id)
    client.access_token = access_token
    return client
