from freeagent_client.token_store import SQLiteTokenStore


def test_sqlite_token_store_round_trip(tmp_path):
    store = SQLiteTokenStore(tmp_path / "tokens.db")
    tokens = {"access_token": "a", "refresh_token": "r", "expires_in": 5}
    store.save(tokens)
    loaded = store.load()
    assert loaded["access_token"] == "a"
    assert loaded["refresh_token"] == "r"
    assert "expires_at" in loaded

