from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
import ssl
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen

from trading_ai.options.tls_context import (
    TLSConfigurationError,
    create_verified_ssl_context,
    resolve_ca_bundle,
)


class LiveOptionDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveOptionContract:
    underlying: str
    contract_ticker: str
    contract_type: str
    expiration_date: str
    strike: float
    dte: int
    bid: float
    ask: float
    midpoint: float
    last_price: float
    entry_price: float
    price_source: str
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float
    open_interest: int
    volume: int
    quote_timestamp: str
    data_source: str
    spread_pct: float


class PolygonOptionSnapshotProvider:
    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 12.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 2.0,
        maximum_pages: int = 2,
        overall_timeout_seconds: float = 45.0,
        progress: bool = True,
    ) -> None:
        if api_key is None:
            from trading_ai.config.settings import settings
            api_key = settings.polygon_api_key

        if not api_key:
            raise LiveOptionDataError("POLYGON_API_KEY is not configured")

        self.api_key = api_key
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.max_retries = max(0, int(max_retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.maximum_pages = max(1, int(maximum_pages))
        self.overall_timeout_seconds = max(
            self.timeout_seconds,
            float(overall_timeout_seconds),
        )
        self.progress = bool(progress)
        try:
            self.ca_bundle = str(resolve_ca_bundle())
            self.ssl_context = create_verified_ssl_context()
        except TLSConfigurationError as exc:
            raise LiveOptionDataError(str(exc)) from exc

    def _log(self, message: str) -> None:
        if self.progress:
            print(
                f"[options] {message}",
                file=sys.stderr,
                flush=True,
            )

    def _with_api_key(
        self,
        path_or_url: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else urljoin(self.BASE_URL, path_or_url)
        )
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(params or {})
        query["apiKey"] = self.api_key
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    def _request_json(
        self,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        *,
        deadline: float,
        page_number: int,
    ) -> dict:
        url = self._with_api_key(path_or_url, params)

        for attempt in range(self.max_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LiveOptionDataError(
                    "Options Snapshot overall deadline exceeded "
                    f"before page {page_number} completed."
                )

            request_timeout = min(self.timeout_seconds, remaining)
            self._log(
                f"fetching page {page_number}, "
                f"attempt {attempt + 1}/{self.max_retries + 1}, "
                f"timeout={request_timeout:.0f}s, "
                f"CA={self.ca_bundle}"
            )

            try:
                request = Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "TradingPlatform/1.0",
                    },
                )
                with urlopen(
                    request,
                    timeout=request_timeout,
                    context=self.ssl_context,
                ) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

                if payload.get("status") == "ERROR":
                    raise LiveOptionDataError(
                        payload.get("error", "Provider error")
                    )
                return payload

            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < self.max_retries:
                    delay = min(
                        self.retry_delay_seconds * (attempt + 1),
                        max(0.0, deadline - time.monotonic()),
                    )
                    self._log(
                        f"rate limited on page {page_number}; "
                        f"retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                if exc.code in {401, 403}:
                    raise LiveOptionDataError(
                        "Options Snapshot access denied. Verify the API "
                        "key and options-snapshot subscription."
                    ) from exc
                raise LiveOptionDataError(
                    f"Options Snapshot HTTP {exc.code}: {body[:500]}"
                ) from exc

            except ssl.SSLCertVerificationError as exc:
                raise LiveOptionDataError(
                    "Options Snapshot TLS verification failed. "
                    f"CA bundle in use: {self.ca_bundle}. "
                    "If a corporate proxy or VPN re-signs HTTPS, set "
                    "TRADING_AI_CA_BUNDLE to a PEM bundle containing "
                    "the corporate root and intermediate CAs. "
                    f"Original error: {exc}"
                ) from exc
            except (URLError, TimeoutError, ssl.SSLError) as exc:
                if attempt < self.max_retries:
                    delay = min(
                        self.retry_delay_seconds * (attempt + 1),
                        max(0.0, deadline - time.monotonic()),
                    )
                    self._log(
                        f"page {page_number} network failure: {exc}; "
                        f"retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                raise LiveOptionDataError(
                    f"Options Snapshot page {page_number} failed "
                    f"after {attempt + 1} attempt(s): {exc}"
                ) from exc

        raise LiveOptionDataError("Options Snapshot request failed")

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _integer(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _timestamp(value: Any) -> str:
        if value in (None, "", 0):
            return ""
        try:
            raw = int(value)
            if raw > 10**17:
                raw /= 1_000_000_000
            elif raw > 10**12:
                raw /= 1_000
            return datetime.fromtimestamp(
                raw,
                tz=timezone.utc,
            ).isoformat()
        except (TypeError, ValueError, OSError):
            return str(value)

    @classmethod
    def _parse_contract(
        cls,
        underlying: str,
        result: dict,
        *,
        as_of: date,
    ) -> LiveOptionContract | None:
        details = result.get("details") or {}
        greeks = result.get("greeks") or {}
        quote = result.get("last_quote") or {}
        trade = result.get("last_trade") or {}
        day = result.get("day") or {}

        ticker = str(details.get("ticker") or "")
        expiration = str(details.get("expiration_date") or "")
        contract_type = str(
            details.get("contract_type") or ""
        ).lower()
        strike = cls._number(details.get("strike_price"))

        if (
            not ticker
            or not expiration
            or strike <= 0
            or contract_type not in {"call", "put"}
        ):
            return None

        bid = cls._number(quote.get("bid"))
        ask = cls._number(quote.get("ask"))
        last_price = cls._number(trade.get("price"))
        day_close = cls._number(day.get("close"))
        fmv = cls._number(result.get("fmv"))

        midpoint = (
            (bid + ask) / 2.0
            if bid > 0 and ask >= bid
            else 0.0
        )
        if midpoint > 0:
            entry_price = midpoint
            price_source = "NBBO_MIDPOINT"
        elif last_price > 0:
            entry_price = last_price
            price_source = "LAST_TRADE"
        elif day_close > 0:
            entry_price = day_close
            price_source = "DAY_CLOSE"
        elif fmv > 0:
            entry_price = fmv
            price_source = "FAIR_MARKET_VALUE"
        else:
            return None

        greek_values = {
            name: cls._number(
                greeks.get(name),
                default=float("nan"),
            )
            for name in ("delta", "gamma", "theta", "vega")
        }
        if not all(
            math.isfinite(value)
            for value in greek_values.values()
        ):
            return None

        try:
            expiry_date = date.fromisoformat(expiration)
        except ValueError:
            return None

        spread_pct = (
            (ask - bid) / midpoint
            if midpoint > 0
            else float("inf")
        )
        timestamp = (
            quote.get("last_updated")
            or quote.get("sip_timestamp")
            or trade.get("sip_timestamp")
            or trade.get("participant_timestamp")
            or result.get("fmv_last_updated")
        )

        return LiveOptionContract(
            underlying=underlying,
            contract_ticker=ticker,
            contract_type=contract_type,
            expiration_date=expiration,
            strike=strike,
            dte=max((expiry_date - as_of).days, 0),
            bid=bid,
            ask=ask,
            midpoint=midpoint,
            last_price=last_price,
            entry_price=entry_price,
            price_source=price_source,
            delta=greek_values["delta"],
            gamma=greek_values["gamma"],
            theta=greek_values["theta"],
            vega=greek_values["vega"],
            rho=cls._number(greeks.get("rho")),
            implied_volatility=cls._number(
                result.get("implied_volatility")
            ),
            open_interest=cls._integer(
                result.get("open_interest")
            ),
            volume=cls._integer(day.get("volume")),
            quote_timestamp=cls._timestamp(timestamp),
            data_source="POLYGON_OPTION_SNAPSHOT",
            spread_pct=spread_pct,
        )

    def chain(
        self,
        underlying: str,
        *,
        signal: str,
        target_expiration: date,
        target_strike: float,
        as_of: date,
        expiration_window_days: int = 10,
        strike_window_pct: float = 0.15,
    ) -> list[LiveOptionContract]:
        started = time.monotonic()
        deadline = started + self.overall_timeout_seconds

        contract_type = (
            "call" if signal.upper() == "CALL" else "put"
        )
        params = {
            "contract_type": contract_type,
            "expiration_date.gte": (
                target_expiration
                - timedelta(days=expiration_window_days)
            ).isoformat(),
            "expiration_date.lte": (
                target_expiration
                + timedelta(days=expiration_window_days)
            ).isoformat(),
            "strike_price.gte": round(
                target_strike * (1.0 - strike_window_pct),
                4,
            ),
            "strike_price.lte": round(
                target_strike * (1.0 + strike_window_pct),
                4,
            ),
            "limit": 250,
            "sort": "expiration_date",
            "order": "asc",
        }

        self._log(
            f"{underlying} {contract_type}: target expiry "
            f"{target_expiration}, target strike {target_strike:.2f}"
        )

        payload = self._request_json(
            f"/v3/snapshot/options/{underlying}",
            params,
            deadline=deadline,
            page_number=1,
        )
        results = list(payload.get("results") or [])
        next_url = payload.get("next_url")
        pages = 1

        self._log(
            f"page 1 returned {len(results)} raw contract(s)"
        )

        while next_url and pages < self.maximum_pages:
            if time.monotonic() >= deadline:
                self._log(
                    "overall deadline reached; using contracts "
                    "already retrieved"
                )
                break

            pages += 1
            page = self._request_json(
                next_url,
                deadline=deadline,
                page_number=pages,
            )
            page_results = list(page.get("results") or [])
            results.extend(page_results)
            next_url = page.get("next_url")
            self._log(
                f"page {pages} returned {len(page_results)} raw "
                f"contract(s); total={len(results)}"
            )

        if next_url:
            self._log(
                f"pagination stopped at configured maximum of "
                f"{self.maximum_pages} page(s)"
            )

        contracts = [
            contract
            for result in results
            if (
                contract := self._parse_contract(
                    underlying,
                    result,
                    as_of=as_of,
                )
            )
            is not None
        ]

        elapsed = time.monotonic() - started
        self._log(
            f"{underlying}: parsed {len(contracts)} usable "
            f"contract(s) in {elapsed:.1f}s"
        )
        return contracts
