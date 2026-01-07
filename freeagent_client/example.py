"""Manual auth + connectivity check helper."""

from __future__ import annotations

import argparse
import json
import sys

from .client import (
    FreeAgentError,
    build_authorize_url,
    check_connection,
    exchange_code_for_tokens,
    get_valid_access_token,
)
from .token_store import FileTokenStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FreeAgent auth helper")
    parser.add_argument("--code", help="Authorization code from redirect")
    parser.add_argument(
        "--token-file",
        default="freeagent_tokens.json",
        help="Path to token storage JSON",
    )
    args = parser.parse_args(argv)

    store = FileTokenStore(args.token_file)

    if not args.code:
        url = build_authorize_url()
        print("Open this URL in your browser and authorize the app:")
        print(url)
        print("Then re-run with --code=<returned_code>")
        return 0

    try:
        tokens = exchange_code_for_tokens(args.code)
        store.save(tokens)
        print("Tokens saved to", args.token_file)
        tokens = get_valid_access_token(store)
        print("Access token ready; checking connection...")
        ok = check_connection(store)
        if ok:
            print("Successfully connected to FreeAgent API")
        else:
            print("Failed to connect to FreeAgent API")
            return 1
        print("Stored tokens:")
        print(json.dumps(store.load(), indent=2))
        return 0
    except FreeAgentError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

