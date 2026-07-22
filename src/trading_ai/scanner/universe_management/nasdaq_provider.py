from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Callable

from .download_manager import ResilientDownloadManager
from .provider_contracts import ProviderFetchResult
from .universe_profile import SecurityProfile


class NasdaqSymbolDirectoryProvider:
    NASDAQ_URLS = (
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    )
    OTHER_URLS = (
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        "https://nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    )

    def __init__(
        self,
        downloader: ResilientDownloadManager | None = None,
        fetch_text: Callable[[str], str] | None = None,
    ) -> None:
        """Create a Nasdaq symbol-directory provider.

        ``fetch_text`` is retained for backward compatibility with the original
        Milestone 35 Step 2 adapter contract and makes deterministic tests
        possible. Production callers continue to use ``ResilientDownloadManager``.
        """
        if downloader is not None and fetch_text is not None:
            raise ValueError("Specify either downloader or fetch_text, not both.")
        self.downloader = downloader or ResilientDownloadManager()
        self.fetch_text = fetch_text

    @property
    def name(self) -> str:
        return "NASDAQ_SYMBOL_DIRECTORY"

    @staticmethod
    def _rows(content: bytes | str) -> list[dict[str, str]]:
        if isinstance(content, bytes):
            text = content.decode("utf-8-sig", errors="replace")
        else:
            text = content.lstrip("\ufeff")
        return list(csv.DictReader(StringIO(text), delimiter="|"))

    def _fetch_compat(self) -> tuple[str, str, str, bool, str]:
        assert self.fetch_text is not None
        nasdaq_url = self.NASDAQ_URLS[0]
        other_url = self.OTHER_URLS[0]
        return (
            self.fetch_text(nasdaq_url),
            self.fetch_text(other_url),
            f"{nasdaq_url};{other_url}",
            False,
            "",
        )

    def _fetch_managed(self) -> tuple[bytes, bytes, str, bool, str]:
        first = self.downloader.fetch(self.NASDAQ_URLS, "nasdaqlisted.txt")
        second = self.downloader.fetch(self.OTHER_URLS, "otherlisted.txt")
        warning = " | ".join(filter(None, (first.warning, second.warning)))
        return (
            first.content,
            second.content,
            f"{first.source_url};{second.source_url}",
            first.from_cache or second.from_cache,
            warning,
        )

    def fetch(self) -> ProviderFetchResult:
        if self.fetch_text is not None:
            nasdaq_content, other_content, source_uri, from_cache, warning = self._fetch_compat()
        else:
            nasdaq_content, other_content, source_uri, from_cache, warning = self._fetch_managed()

        securities: list[SecurityProfile] = []
        for row in self._rows(nasdaq_content):
            symbol = (row.get("Symbol") or "").strip()
            if not symbol or symbol.startswith("File Creation Time") or row.get("Test Issue") == "Y":
                continue
            securities.append(
                SecurityProfile(
                    symbol=symbol,
                    name=(row.get("Security Name") or "").strip(),
                    exchange="NASDAQ",
                    asset_type="ETF" if row.get("ETF") == "Y" else "EQUITY",
                    active=True,
                    tradable=True,
                    source=self.name,
                )
            )

        exchange_map = {
            "N": "NYSE",
            "A": "NYSE_AMERICAN",
            "P": "NYSE_ARCA",
            "Z": "CBOE",
            "V": "NASDAQ",
        }
        for row in self._rows(other_content):
            symbol = (row.get("ACT Symbol") or "").strip()
            if not symbol or symbol.startswith("File Creation Time") or row.get("Test Issue") == "Y":
                continue
            securities.append(
                SecurityProfile(
                    symbol=symbol,
                    name=(row.get("Security Name") or "").strip(),
                    exchange=exchange_map.get((row.get("Exchange") or "").strip(), "NYSE"),
                    asset_type="ETF" if row.get("ETF") == "Y" else "EQUITY",
                    active=True,
                    tradable=True,
                    source=self.name,
                )
            )

        return ProviderFetchResult(
            self.name,
            tuple(securities),
            datetime.now(timezone.utc),
            success=True,
            from_cache=from_cache,
            source_uri=source_uri,
            warning=warning,
        )
