# FreeAgent Client

Lightweight FreeAgent API helper packaged as `freeagent_client` with pluggable token storage.

## Install

```bash
pip install -e .
```

## Environment variables

Create a `.env` file in the project root with values from your FreeAgent app settings:

```
FREEAGENT_CLIENT_ID=...
FREEAGENT_CLIENT_SECRET=...
FREEAGENT_REDIRECT_URI=http://localhost:5000
```

## Auth flow (manual)

1) Print the authorize URL:

```bash
freeagent-auth
```

2) Open the URL, approve, and capture the `code` from the redirect.

3) Exchange and store tokens:

```bash
freeagent-auth --code "<returned_code>"
```

Tokens are saved to `freeagent_tokens.json` by default; override with `--token-file` if you want to persist elsewhere (e.g., for DB storage you can re-implement `TokenStore`).

## Usage

```python
from freeagent_client import (
    FileTokenStore,
    SQLiteTokenStore,
    build_authorize_url,
    exchange_code_for_tokens,
    get_valid_access_token,
    get_invoice,
    create_expense,
    create_invoice,
)

store = FileTokenStore()

# First-time auth (once)
print(build_authorize_url())
tokens = exchange_code_for_tokens("code-from-redirect")
store.save(tokens)

# Later usage
tokens = get_valid_access_token(store)  # auto-refresh if expired
invoice = get_invoice("123", store)
expense = create_expense(
    description="Lunch",
    amount="12.50",
    store=store,
)
```

You can implement your own `TokenStore` to read/write tokens from any backend. Methods are `load() -> Optional[dict]` and `save(tokens: dict) -> None`.

### Using a database-backed token store

Built-in option for quick DB persistence:

```python
from freeagent_client import SQLiteTokenStore, get_valid_access_token

store = SQLiteTokenStore("freeagent_tokens.db")
tokens = get_valid_access_token(store)
```

Custom store example (e.g., Postgres) in your app:

```python
import time

from freeagent_client import TokenStore

class PostgresTokenStore(TokenStore):
    def __init__(self, pool):  # pass in your DB pool/engine
        self.pool = pool

    def load(self):
        row = self.pool.fetchrow("select data from tokens where id=1")
        return None if not row else row["data"]

    def save(self, tokens):
        # ensure expires_at exists if using expires_in
        if "expires_in" in tokens and "expires_at" not in tokens:
            tokens["expires_at"] = int(time.time()) + int(tokens["expires_in"])
        self.pool.execute(
            \"\"\"\n+            insert into tokens(id, data)\n+            values (1, :data)\n+            on conflict (id) do update set data = excluded.data\n+            \"\"\",\n+            {\"data\": tokens},\n+        )
```

Wire `store` into all client calls; no other changes needed.

## Tests

```bash
pip install -e .[dev]
pytest
```

## Local connectivity check

After exporting env vars:

```bash
pip install -e .
freeagent-auth           # prints authorize URL
freeagent-auth --code "<returned_code>"  # saves tokens and checks /v2/users/me
```

## Features
- `build_authorize_url()`: generate the FreeAgent authorize URL for browser-based consent.
- `exchange_code_for_tokens(code, redirect_uri=None)`: swap an auth code for access/refresh tokens (computes `expires_at`).
- `refresh_access_token(refresh_token)`: refresh and return a new token set.
- `get_valid_access_token(store)`: load tokens from the configured store and auto-refresh if expired.
- `check_connection(store)`: quick `/v2/users/me` connectivity check.
- `get_current_user(store)`: fetch current user details (full user payload).
- `get_price_list_items(store, sort="-created_at")`: list price list items (newest first by default).
- `get_contacts(store, sort="-created_at")`: list contacts (newest first by default).
- `get_invoice(invoice_id, store)`: fetch an invoice by ID.
- `create_expense(...)`: create an expense (supports VAT, attachments with basic MIME validation, category code selection).
- `create_invoice(...)`: create an invoice with contact, status (Draft), dates/terms, currency, comments, and line items.
- `attach_to_expense(expense_id, file_path, store)`: attach a file to an existing expense.
- Token stores: `FileTokenStore` (JSON file), `SQLiteTokenStore` (local DB), or bring your own by implementing `TokenStore` (`load`/`save`).

### Creating an invoice

```python
from freeagent_client import create_invoice, FileTokenStore

store = FileTokenStore()
items = [
    {
        "description": "Consulting",
        "price": "500.00",
        "quantity": "1",
        "item_type": "Services",  # per FreeAgent docs
    }
]
invoice = create_invoice(
    contact_url="https://api.freeagent.com/v2/contacts/123",
    dated_on="2024-05-01",
    payment_terms_in_days=14,  # due date offset
    currency="GBP",
    items=items,
    comments="Thanks for your business",
    store=store,
)
```

To test locally: run the auth helper to get tokens (`freeagent-auth --code ...`), then call `create_invoice` with real contact URLs and item data from your FreeAgent account. The function returns the API response JSON so you can inspect the result.
