"""Constants and checks shared by the service tests (AKS-110)."""

PORT = 8765
TOKEN = "test-token-0123456789"
BASE_URL = f"http://127.0.0.1:{PORT}"
WS_URL = f"ws://127.0.0.1:{PORT}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def assert_error(body: object, code: str) -> None:
    """``body`` is spec 3's error body with ``code``."""
    assert isinstance(body, dict)
    assert set(body) == {"error", "issues"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    assert isinstance(body["issues"], list)
