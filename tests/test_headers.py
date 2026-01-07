from freeagent_client.client import _build_headers


def test_build_headers_standard():
    headers = _build_headers("token")
    assert headers["Authorization"] == "Bearer token"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


def test_build_headers_attachment():
    headers = _build_headers("token", attachment=True)
    assert headers["Authorization"] == "Bearer token"
    assert headers.get("Content-Type") is None
    assert headers["Accept"] == "application/json"

