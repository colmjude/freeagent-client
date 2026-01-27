from freeagent_client.client import get_invoices, FreeAgentError


class DummyStore:
    def __init__(self):
        self.tokens = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_at": 9999999999,
        }

    def load(self):
        return self.tokens

    def save(self, tokens):
        self.tokens = tokens


def test_get_invoices_params(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, params=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params

        class Resp:
            status_code = 200

            def json(self):
                return {"invoices": []}

        return Resp()

    monkeypatch.setattr("freeagent_client.client.requests.get", fake_get)
    store = DummyStore()
    get_invoices(
        store,
        last_n_months=3,
        updated_since="2024-01-01T00:00:00Z",
        sort="-updated_at",
    )

    assert captured["params"]["view"] == "last_3_months"
    assert captured["params"]["updated_since"] == "2024-01-01T00:00:00Z"
    assert captured["params"]["sort"] == "-updated_at"


def test_get_invoices_invalid_sort():
    store = DummyStore()
    try:
        get_invoices(store, sort="bad")
    except FreeAgentError as exc:
        assert "Invalid sort" in str(exc)
    else:
        raise AssertionError("Expected FreeAgentError for invalid sort")

