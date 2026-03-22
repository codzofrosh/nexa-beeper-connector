import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from bridge.adapters.mautrix import MautrixConfig, MautrixSender


class _RecordingHandler(BaseHTTPRequestHandler):
    requests = []
    response_code = 200
    response_body = {"event_id": "$event:test"}

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.__class__.requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )
        payload = json.dumps(self.__class__.response_body).encode("utf-8")
        self.send_response(self.__class__.response_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


@pytest.fixture
def matrix_server():
    _RecordingHandler.requests = []
    _RecordingHandler.response_code = 200
    _RecordingHandler.response_body = {"event_id": "$event:test"}
    server = HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", _RecordingHandler
    finally:
        server.shutdown()
        thread.join()


def test_send_text_uses_matrix_send_endpoint_and_auth(matrix_server):
    base_url, handler = matrix_server
    sender = MautrixSender(
        MautrixConfig(
            homeserver_url=base_url,
            access_token="secret-token",
            sender_user_id="@bridgebot:example.com",
        )
    )

    event_id = sender.send_text(
        room_id="!room:example.com",
        text="hello from bridge",
        txn_id="txn-123",
    )

    assert event_id == "$event:test"
    assert len(handler.requests) == 1
    recorded = handler.requests[0]
    assert recorded["path"].startswith(
        "/_matrix/client/v3/rooms/%21room%3Aexample.com/send/m.room.message/txn-123"
    )
    assert "user_id=%40bridgebot%3Aexample.com" in recorded["path"]
    assert recorded["headers"]["Authorization"] == "Bearer secret-token"
    assert json.loads(recorded["body"]) == {
        "msgtype": "m.text",
        "body": "hello from bridge",
    }


def test_send_text_raises_on_http_error(matrix_server):
    base_url, handler = matrix_server
    handler.response_code = 401
    handler.response_body = {"errcode": "M_UNKNOWN_TOKEN", "error": "Bad token"}
    sender = MautrixSender(
        MautrixConfig(
            homeserver_url=base_url,
            access_token="bad-token",
        )
    )

    with pytest.raises(RuntimeError, match="HTTP 401"):
        sender.send_text(
            room_id="!room:example.com",
            text="hello from bridge",
            txn_id="txn-401",
        )
