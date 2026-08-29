from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import Request, urlopen

from trading_ai.options.tls_context import (
    create_verified_ssl_context,
    resolve_ca_bundle,
)


def main() -> None:
    request = Request(
        "https://api.polygon.io/",
        headers={"User-Agent": "TradingPlatform-TLS-Check/1.0"},
    )
    try:
        with urlopen(
            request,
            timeout=12,
            context=create_verified_ssl_context(),
        ) as response:
            print(f"HTTP status: {response.status}")
    except HTTPError as exc:
        print(f"HTTP status: {exc.code}")
    print(f"CA bundle: {resolve_ca_bundle()}")
    print("TLS handshake with api.polygon.io succeeded.")


if __name__ == "__main__":
    main()
