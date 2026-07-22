from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse

import requests

from trading_ai.scanner.options_market_data_quality.contracts import (
    OptionContractIdentity,
    OptionQuoteRecord,
    OptionSide,
)
from .contracts import ProviderBatch


@dataclass(frozen=True)
class PolygonSnapshotPolicy:
    minimum_dte: int = 0
    maximum_dte: int = 365
    minimum_open_interest: int = 0
    minimum_volume: int = 0
    maximum_strike_distance_pct: float | None = 0.40
    request_limit: int = 250
    timeout_seconds: float = 30.0
    maximum_attempts: int = 6
    initial_backoff_seconds: float = 1.0
    maximum_backoff_seconds: float = 30.0
    requests_per_second: float = 4.0

    def validate(self) -> None:
        if self.minimum_dte < 0 or self.maximum_dte < self.minimum_dte:
            raise ValueError("invalid DTE range")
        if self.minimum_open_interest < 0 or self.minimum_volume < 0:
            raise ValueError("liquidity thresholds cannot be negative")
        if self.request_limit <= 0 or self.maximum_attempts <= 0:
            raise ValueError("request_limit and maximum_attempts must be positive")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")


class PolygonOptionSnapshotMapper:
    def map(self, underlying_symbol: str, quote_date: date, payload: Mapping[str, Any]) -> OptionQuoteRecord:
        details = payload.get("details") or {}
        quote = payload.get("last_quote") or {}
        trade = payload.get("last_trade") or {}
        day = payload.get("day") or {}
        greeks = payload.get("greeks") or {}
        contract_type = str(details.get("contract_type", "")).upper()
        if contract_type == "CALL":
            side = OptionSide.CALL
        elif contract_type == "PUT":
            side = OptionSide.PUT
        else:
            raise ValueError(f"unsupported contract_type: {contract_type!r}")

        expiration = date.fromisoformat(str(details["expiration_date"]))
        strike = float(details["strike_price"])
        return OptionQuoteRecord(
            identity=OptionContractIdentity(
                underlying_symbol=underlying_symbol.strip().upper(),
                expiration_date=expiration,
                strike=strike,
                option_side=side,
            ),
            quote_date=quote_date,
            bid=self._number(quote.get("bid")),
            ask=self._number(quote.get("ask")),
            last=self._number(trade.get("price", day.get("close"))),
            volume=self._integer(day.get("volume")),
            open_interest=self._integer(payload.get("open_interest")),
            implied_volatility=self._number(payload.get("implied_volatility")),
            delta=self._number(greeks.get("delta")),
            gamma=self._number(greeks.get("gamma")),
            theta=self._number(greeks.get("theta")),
            vega=self._number(greeks.get("vega")),
            provider_symbol=details.get("ticker"),
            metadata={
                "source": "polygon_option_chain_snapshot",
                "underlying_price": self._number((payload.get("underlying_asset") or {}).get("price")),
                "break_even_price": self._number(payload.get("break_even_price")),
            },
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _integer(value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(float(value))


class PolygonOptionChainSnapshotProvider:
    BASE_URL = "https://api.polygon.io/v3/snapshot/options"

    def __init__(
        self,
        api_key: str,
        *,
        as_of_date: date | None = None,
        policy: PolygonSnapshotPolicy | None = None,
        session: requests.Session | None = None,
        mapper: PolygonOptionSnapshotMapper | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Polygon API key is required")
        self.api_key = api_key.strip()
        self.as_of_date = as_of_date or date.today()
        self.policy = policy or PolygonSnapshotPolicy()
        self.policy.validate()
        self.session = session or requests.Session()
        self.mapper = mapper or PolygonOptionSnapshotMapper()
        self.sleep = sleep
        self._last_request_time = 0.0

    @property
    def source_name(self) -> str:
        return "polygon_option_chain_snapshot"

    def iter_batches(
        self,
        *,
        symbols: Sequence[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        batch_size: int = 5_000,
    ) -> Iterable[ProviderBatch]:
        del start_date, end_date
        if not symbols:
            raise ValueError("symbols are required for Polygon snapshot capture")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        for symbol in sorted({s.strip().upper() for s in symbols if s and s.strip()}):
            records: list[OptionQuoteRecord] = []
            page = 0
            for payload in self._iter_symbol_payloads(symbol):
                try:
                    record = self.mapper.map(symbol, self.as_of_date, payload)
                except (KeyError, TypeError, ValueError):
                    continue
                if not self._accept(record):
                    continue
                records.append(record)
                if len(records) >= batch_size:
                    page += 1
                    yield ProviderBatch(
                        batch_id=f"polygon:{self.as_of_date.isoformat()}:{symbol}:{page}",
                        records=tuple(records),
                        source_name=self.source_name,
                        metadata={"symbol": symbol, "capture_date": self.as_of_date.isoformat()},
                    )
                    records = []
            if records:
                page += 1
                yield ProviderBatch(
                    batch_id=f"polygon:{self.as_of_date.isoformat()}:{symbol}:{page}",
                    records=tuple(records),
                    source_name=self.source_name,
                    metadata={"symbol": symbol, "capture_date": self.as_of_date.isoformat()},
                )

    def _iter_symbol_payloads(self, symbol: str) -> Iterable[Mapping[str, Any]]:
        url = f"{self.BASE_URL}/{symbol}"
        params: dict[str, Any] | None = {
            "expiration_date.gte": date.fromordinal(self.as_of_date.toordinal() + self.policy.minimum_dte).isoformat(),
            "expiration_date.lte": date.fromordinal(self.as_of_date.toordinal() + self.policy.maximum_dte).isoformat(),
            "limit": self.policy.request_limit,
            "sort": "expiration_date",
            "order": "asc",
        }
        while url:
            payload = self._request_json(url, params=params)
            for item in payload.get("results") or ():
                if isinstance(item, Mapping):
                    yield item
            next_url = payload.get("next_url")
            url = str(next_url) if next_url else ""
            params = None

    def _request_json(self, url: str, *, params: Mapping[str, Any] | None) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.policy.maximum_attempts + 1):
            self._throttle()
            request_params = dict(params or {})
            request_params["apiKey"] = self.api_key
            try:
                response = self.session.get(url, params=request_params, timeout=self.policy.timeout_seconds)
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(f"retryable Polygon HTTP {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, Mapping):
                    raise ValueError("Polygon response must be a JSON object")
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.policy.maximum_attempts:
                    break
                delay = min(
                    self.policy.maximum_backoff_seconds,
                    self.policy.initial_backoff_seconds * (2 ** (attempt - 1)),
                )
                self.sleep(delay + random.uniform(0.0, min(0.5, delay / 4)))
        raise RuntimeError(f"Polygon request failed after retries: {last_error}")

    def _throttle(self) -> None:
        minimum_interval = 1.0 / self.policy.requests_per_second
        elapsed = time.monotonic() - self._last_request_time
        if self._last_request_time and elapsed < minimum_interval:
            self.sleep(minimum_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _accept(self, record: OptionQuoteRecord) -> bool:
        dte = record.days_to_expiration
        if dte < self.policy.minimum_dte or dte > self.policy.maximum_dte:
            return False
        if (record.open_interest or 0) < self.policy.minimum_open_interest:
            return False
        if (record.volume or 0) < self.policy.minimum_volume:
            return False
        threshold = self.policy.maximum_strike_distance_pct
        underlying_price = record.metadata.get("underlying_price") if record.metadata else None
        if threshold is not None and underlying_price is not None and float(underlying_price) > 0:
            distance = abs(record.identity.strike - float(underlying_price)) / float(underlying_price)
            if distance > threshold:
                return False
        return True
