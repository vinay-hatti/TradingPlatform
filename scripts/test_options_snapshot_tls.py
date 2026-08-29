from __future__ import annotations

import ssl

from trading_ai.options.tls_context import (
    create_verified_ssl_context,
    resolve_ca_bundle,
)


def main() -> None:
    bundle = resolve_ca_bundle()
    context = create_verified_ssl_context()
    assert bundle.is_file()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    print(f"CA bundle: {bundle}")
    print("TLS verification mode: CERT_REQUIRED")
    print("Hostname verification: enabled")
    print("All options-snapshot TLS assertions passed.")


if __name__ == "__main__":
    main()
