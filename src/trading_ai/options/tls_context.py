from __future__ import annotations

import os
from pathlib import Path
import ssl


class TLSConfigurationError(RuntimeError):
    pass


def resolve_ca_bundle() -> Path:
    for variable in (
        "TRADING_AI_CA_BUNDLE",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
    ):
        value = os.getenv(variable)
        if value:
            path = Path(value).expanduser().resolve()
            if not path.is_file():
                raise TLSConfigurationError(
                    f"{variable} points to a missing CA bundle: {path}"
                )
            return path

    try:
        import certifi
        path = Path(certifi.where()).resolve()
        if path.is_file():
            return path
    except ImportError:
        pass

    defaults = ssl.get_default_verify_paths()
    if defaults.cafile:
        path = Path(defaults.cafile)
        if path.is_file():
            return path.resolve()

    raise TLSConfigurationError(
        "No trusted CA bundle found. Run `uv add certifi`, or set "
        "TRADING_AI_CA_BUNDLE to a PEM CA bundle."
    )


def create_verified_ssl_context() -> ssl.SSLContext:
    bundle = resolve_ca_bundle()
    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=str(bundle),
    )
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context
