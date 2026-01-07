import time

from freeagent_client.token_store import FileTokenStore


def test_file_token_store_round_trip(tmp_path):
    store = FileTokenStore(tmp_path / "tokens.json")
    tokens = {"access_token": "a", "refresh_token": "r", "expires_in": 5}
    store.save(tokens)
    loaded = store.load()
    assert loaded["access_token"] == "a"
    assert loaded["refresh_token"] == "r"
    assert "expires_at" in loaded
    assert loaded["expires_at"] >= int(time.time())

