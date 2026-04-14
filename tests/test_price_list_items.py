from freeagent_client.client import create_price_list_item, get_price_list_items


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


def test_get_price_list_items_params(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, params=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params

        class Resp:
            status_code = 200

            def json(self):
                return {"price_list_items": []}

        return Resp()

    monkeypatch.setattr("freeagent_client.client.requests.get", fake_get)
    store = DummyStore()
    get_price_list_items(store, sort="-created_at")

    assert captured["params"]["sort"] == "-created_at"


def test_create_price_list_item_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json

        class Resp:
            status_code = 201

            def json(self):
                return {"price_list_item": {"code": "CONSULTING_DAY"}}

        return Resp()

    monkeypatch.setattr("freeagent_client.client.requests.post", fake_post)
    store = DummyStore()
    result = create_price_list_item(
        code="CONSULTING_DAY",
        description="Consulting day rate",
        item_type="Products",
        price="750.00",
        quantity="1.0",
        vat_status="20.0%",
        store=store,
    )

    assert result["price_list_item"]["code"] == "CONSULTING_DAY"
    assert captured["json"]["price_list_item"]["code"] == "CONSULTING_DAY"
    assert captured["json"]["price_list_item"]["description"] == "Consulting day rate"
    assert captured["json"]["price_list_item"]["item_type"] == "Products"
    assert captured["json"]["price_list_item"]["price"] == "750.00"
    assert captured["json"]["price_list_item"]["quantity"] == "1.0"
    assert captured["json"]["price_list_item"]["vat_status"] == "20.0%"
