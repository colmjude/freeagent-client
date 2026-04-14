"""Core FreeAgent client functions with pluggable token storage."""

from __future__ import annotations

import base64
import mimetypes
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional

import os

from dotenv import load_dotenv
import requests

from .token_store import TokenStore, TokenDict

FREEAGENT_BASE = "https://api.freeagent.com/v2"
TOKEN_ENDPOINT = f"{FREEAGENT_BASE}/token_endpoint"
USER_URL = f"{FREEAGENT_BASE}/users/me"
INVOICES_URL = f"{FREEAGENT_BASE}/invoices"
EXPENSES_URL = f"{FREEAGENT_BASE}/expenses"
PRICE_LIST_ITEMS_URL = f"{FREEAGENT_BASE}/price_list_items"
CONTACTS_URL = f"{FREEAGENT_BASE}/contacts"
BANK_ACCOUNTS_URL = f"{FREEAGENT_BASE}/bank_accounts"

# Load .env values once so callers can rely on local files without shell exports.
load_dotenv()


class FreeAgentError(Exception):
    """Raised for FreeAgent client errors."""


def _env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise FreeAgentError(f"Environment variable {name} is required")
    return val


def _build_headers(access_token: str, *, attachment: bool = False) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if not attachment:
        headers["Content-Type"] = "application/json"
    return headers


def exchange_code_for_tokens(code: str, redirect_uri: Optional[str] = None) -> TokenDict:
    client_id = _env("FREEAGENT_CLIENT_ID")
    client_secret = _env("FREEAGENT_CLIENT_SECRET")
    redirect = redirect_uri or _env("FREEAGENT_REDIRECT_URI")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
    }
    resp = requests.post(TOKEN_ENDPOINT, data=data)
    tokens = resp.json()
    if "error" in tokens:
        raise FreeAgentError(f"Error in token response: {tokens['error']}")
    tokens["expires_at"] = int(time.time()) + int(tokens["expires_in"])
    return tokens


def refresh_access_token(refresh_token: str) -> TokenDict:
    client_id = _env("FREEAGENT_CLIENT_ID")
    client_secret = _env("FREEAGENT_CLIENT_SECRET")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    resp = requests.post(TOKEN_ENDPOINT, data=data)
    tokens = resp.json()
    if "error" in tokens:
        raise FreeAgentError(f"Error in token refresh: {tokens['error']}")
    tokens["expires_at"] = int(time.time()) + int(tokens["expires_in"])
    return tokens


def get_valid_access_token(store: TokenStore) -> TokenDict:
    tokens = store.load()
    if not tokens:
        raise FreeAgentError("No stored tokens; run auth flow first")
    now = int(time.time())
    if now >= int(tokens.get("expires_at", 0)):
        tokens = refresh_access_token(tokens["refresh_token"])
        store.save(tokens)
    return tokens


def check_connection(store: TokenStore) -> bool:
    try:
        tokens = get_valid_access_token(store)
    except FreeAgentError:
        return False

    headers = _build_headers(tokens["access_token"])
    resp = requests.get(USER_URL, headers=headers)
    return resp.status_code == 200


def get_invoice(invoice_id: str, store: TokenStore) -> Dict:
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    resp = requests.get(f"{INVOICES_URL}/{invoice_id}", headers=headers)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get invoice. Status code: {resp.status_code}, Response: {resp.text}"
    )

def get_invoices(
    store: TokenStore,
    *,
    last_n_months: int | None = None,
    updated_since: str | None = None,
    open_only: bool = False,
    sort: str = "created_at",
    per_page: int = 25,
    page: int = 1,
) -> Dict:
    """Fetch invoices with optional filters and sorting."""
    allowed_sorts = {"created_at", "updated_at", "-created_at", "-updated_at"}
    if sort not in allowed_sorts:
        raise FreeAgentError(f"Invalid sort '{sort}'. Must be one of {sorted(allowed_sorts)}")
    if per_page < 1 or per_page > 100:
        raise FreeAgentError("per_page must be between 1 and 100")
    if page < 1:
        raise FreeAgentError("page must be 1 or greater")

    view = None
    if last_n_months is not None:
        view = f"last_{last_n_months}_months"
    if open_only:
        if view:
            raise FreeAgentError("Only one view filter can be used at a time")
        view = "open"

    params = {"sort": sort, "per_page": per_page, "page": page}
    if view:
        params["view"] = view
    if updated_since:
        params["updated_since"] = updated_since

    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    resp = requests.get(INVOICES_URL, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get invoices. Status code: {resp.status_code}, Response: {resp.text}"
    )

def get_invoice_pdf(invoice_id: str, store: TokenStore, *, as_base64: bool = False):
    """Fetch an invoice PDF; return bytes or base64 string for direct storage."""
    tokens = get_valid_access_token(store)
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/pdf",
    }
    resp = requests.get(
        f"{INVOICES_URL}/{invoice_id}/pdf", headers=headers
    )
    if resp.status_code == 200:
        return (
            base64.b64encode(resp.content).decode()
            if as_base64
            else resp.content
        )
    raise FreeAgentError(
        f"Failed to get invoice PDF. Status code: {resp.status_code}, Response: {resp.text}"
    )


def get_current_user(store: TokenStore) -> str:
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    resp = requests.get(USER_URL, headers=headers)
    if resp.status_code == 200:
        return resp.json()["user"]
    raise FreeAgentError(
        f"Failed to get user info. Status code: {resp.status_code}, Response: {resp.text}"
    )


def get_price_list_items(store: TokenStore, sort: str = "-created_at") -> Dict:
    """Fetch price list items; defaults to newest first via `sort=-created_at`."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    params = {"sort": sort} if sort else None
    resp = requests.get(PRICE_LIST_ITEMS_URL, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get price list items. Status code: {resp.status_code}, Response: {resp.text}"
    )


def create_price_list_item(
    *,
    code: str,
    description: str,
    item_type: str,
    price: str,
    quantity: str,
    store: TokenStore,
    vat_status: str | None = None,
    sales_tax_rate: str | None = None,
    second_sales_tax_rate: str | None = None,
    category: str | None = None,
    stock_item: str | None = None,
) -> Dict:
    """Create a price list item."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])

    payload: Dict[str, Dict[str, str]] = {
        "price_list_item": {
            "code": code,
            "description": description,
            "item_type": item_type,
            "price": price,
            "quantity": quantity,
        }
    }
    if vat_status is not None:
        payload["price_list_item"]["vat_status"] = vat_status
    if sales_tax_rate is not None:
        payload["price_list_item"]["sales_tax_rate"] = sales_tax_rate
    if second_sales_tax_rate is not None:
        payload["price_list_item"]["second_sales_tax_rate"] = second_sales_tax_rate
    if category is not None:
        payload["price_list_item"]["category"] = category
    if stock_item is not None:
        payload["price_list_item"]["stock_item"] = stock_item

    resp = requests.post(PRICE_LIST_ITEMS_URL, headers=headers, json=payload)
    if resp.status_code == 201:
        return resp.json()
    raise FreeAgentError(
        f"Failed to create price list item. Status code: {resp.status_code}, Response: {resp.text}"
    )


def get_contacts(store: TokenStore, sort: str = "-created_at") -> Dict:
    """Fetch contacts; defaults to newest first via `sort=-created_at`."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    params = {"sort": sort} if sort else None
    resp = requests.get(CONTACTS_URL, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get contacts. Status code: {resp.status_code}, Response: {resp.text}"
    )

def get_bank_accounts(store: TokenStore) -> Dict:
    """Fetch list of bank accounts."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    resp = requests.get(BANK_ACCOUNTS_URL, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get bank accounts. Status code: {resp.status_code}, Response: {resp.text}"
    )

def get_bank_account(account_id: str, store: TokenStore) -> Dict:
    """Fetch details for a specific bank account by ID."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])
    resp = requests.get(f"{BANK_ACCOUNTS_URL}/{account_id}", headers=headers)
    if resp.status_code == 200:
        return resp.json()
    raise FreeAgentError(
        f"Failed to get bank account. Status code: {resp.status_code}, Response: {resp.text}"
    )

def create_invoice(
    *,
    contact_url: str,
    dated_on: str,
    payment_terms_in_days: int,
    currency: str,
    items: list[Dict],
    store: TokenStore,
    status: str = "Draft",
    comments: str | None = None,
) -> Dict:
    """Create an invoice with basic fields and line items."""
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])

    payload = {
        "invoice": {
            "contact": contact_url,
            "status": status,
            "dated_on": dated_on,
            "payment_terms_in_days": payment_terms_in_days,
            "currency": currency,
            "invoice_items": items,
        }
    }
    if comments:
        payload["invoice"]["comments"] = comments

    resp = requests.post(INVOICES_URL, headers=headers, json=payload)
    if resp.status_code == 201:
        return resp.json()
    raise FreeAgentError(
        f"Failed to create invoice. Status code: {resp.status_code}, Response: {resp.text}"
    )


def _encode_file_to_base64(file_path: str | Path) -> tuple[str, str]:
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "image/jpeg"
    elif mime_type not in {
        "image/png",
        "image/x-png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "application/x-pdf",
        "application/pdf",
    }:
        raise FreeAgentError(f"Unsupported file type: {mime_type}")

    with open(file_path, "rb") as f:
        file_data = f.read()
    return base64.b64encode(file_data).decode(), mime_type


def create_expense(
    *,
    description: str,
    amount: str,
    store: TokenStore,
    dated_on: Optional[str] = None,
    currency: str = "GBP",
    vat_amount: Optional[str] = None,
    items: Optional[str] = None,
    attachment_path: Optional[str | Path] = None,
    category_code: str = "285",
) -> Dict:
    category_url = f"{FREEAGENT_BASE}/categories/{category_code}"
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"])

    user_url = get_current_user(store)

    full_description = description
    if items:
        full_description = f"{description} - Items: {items}"

    expense_data = {
        "expense": {
            "user": user_url,
            "category": category_url,
            "dated_on": dated_on or date.today().isoformat(),
            "description": full_description,
            "gross_value": amount,
            "currency": currency,
        }
    }

    if vat_amount is not None:
        expense_data["expense"]["manual_sales_tax_amount"] = vat_amount

    if attachment_path:
        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FreeAgentError(f"Attachment file not found: {attachment_path}")
        base64_data, content_type = _encode_file_to_base64(file_path)
        expense_data["expense"]["attachment"] = {
            "data": base64_data,
            "file_name": file_path.name,
            "description": "Receipt photo",
            "content_type": content_type,
        }

    resp = requests.post(EXPENSES_URL, headers=headers, json=expense_data)
    if resp.status_code == 201:
        return resp.json()
    raise FreeAgentError(
        f"Failed to create expense. Status code: {resp.status_code}, Response: {resp.text}"
    )


def attach_to_expense(expense_id: str, file_path: str | Path, store: TokenStore) -> Dict:
    tokens = get_valid_access_token(store)
    headers = _build_headers(tokens["access_token"], attachment=True)

    expense_url = f"{EXPENSES_URL}/{expense_id}"
    file_name = Path(file_path).name

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "image/jpeg"

    with open(file_path, "rb") as f:
        files = {
            "attachment[attached-to]": (None, expense_url),
            "attachment[description]": (None, f"Receipt photo - {file_name}"),
            "attachment[content]": (str(file_path), f, mime_type),
        }
        resp = requests.post(f"{FREEAGENT_BASE}/attachments", headers=headers, files=files)

    if resp.status_code == 201:
        return resp.json()
    raise FreeAgentError(
        f"Failed to attach file. Status code: {resp.status_code}, Response: {resp.text}"
    )


def build_authorize_url(state: str = "") -> str:
    client_id = _env("FREEAGENT_CLIENT_ID")
    redirect_uri = _env("FREEAGENT_REDIRECT_URI")
    return (
        "https://api.freeagent.com/v2/approve_app?response_type=code"
        f"&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
    )
