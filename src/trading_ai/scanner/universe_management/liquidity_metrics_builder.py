from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, inspect, select


@dataclass(frozen=True)
class LiquidityMetricsBuildPolicy:
    lookback_trading_days: int = 20
    calendar_lookback_days: int = 45
    batch_size: int = 500
    minimum_price_observations: int = 5
    require_price_history: bool = True


@dataclass(frozen=True)
class LiquidityMetricsBuildResult:
    generated_at: datetime
    status: str
    universe_count: int
    metrics_count: int
    missing_price_count: int
    missing_reference_count: int
    missing_option_count: int
    output_csv: str
    manifest_json: str
    diagnostics_json: str
    sha256: str
    diagnostics: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class LiquidityMetricsBuilder:
    """Build Step-4 liquidity metrics from repository-native market data.

    Price history is mandatory by policy. Reference and option data are optional
    enrichments: their absence is represented as blank fields and diagnostics,
    never as fabricated zeroes.
    """

    OUTPUT_FIELDS = (
        "symbol", "as_of", "price", "average_daily_volume",
        "average_daily_dollar_volume", "bid_ask_spread_pct", "market_cap",
        "option_volume", "option_open_interest", "halted",
    )

    PRICE_ALIASES = {
        "symbol": ("symbol", "ticker"), "date": ("date", "trade_date", "as_of"),
        "close": ("close", "adj_close", "price"), "volume": ("volume",),
    }
    OPTION_ALIASES = {
        "symbol": ("underlying_symbol", "symbol", "underlying"),
        "quote_date": ("quote_date", "date", "as_of_date"),
        "bid": ("bid",), "ask": ("ask",), "volume": ("volume",),
        "open_interest": ("open_interest", "openinterest", "oi"),
    }
    PRICE_TABLES = ("price_history", "market_price_history", "prices")
    OPTION_TABLES = (
        "option_contract_history", "option_chain_history", "option_history",
        "option_chain", "options_history",
    )

    def __init__(self, policy: LiquidityMetricsBuildPolicy | None = None) -> None:
        self.policy = policy or LiquidityMetricsBuildPolicy()

    @staticmethod
    def _normalize_symbols(rows: Iterable[dict[str, Any]]) -> list[str]:
        return list(dict.fromkeys(
            str(row.get("symbol") or row.get("ticker") or "").strip().upper()
            for row in rows
            if str(row.get("symbol") or row.get("ticker") or "").strip()
        ))

    @staticmethod
    def _read_csv(path: str | Path | None) -> list[dict[str, str]]:
        if not path:
            return []
        source = Path(path)
        if not source.is_file():
            return []
        with source.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _alias(columns: set[str], aliases: tuple[str, ...]) -> str | None:
        lowered = {name.lower(): name for name in columns}
        for alias in aliases:
            if alias.lower() in lowered:
                return lowered[alias.lower()]
        return None

    def _resolve_table(self, session, preferred: tuple[str, ...], aliases: dict[str, tuple[str, ...]], required: set[str]):
        inspector = inspect(session.get_bind())
        names = inspector.get_table_names()
        ordered = [name for name in preferred if name in names] + [name for name in names if name not in preferred]
        for name in ordered:
            columns = {item["name"] for item in inspector.get_columns(name)}
            mapping = {canonical: self._alias(columns, choices) for canonical, choices in aliases.items()}
            if any(mapping[key] is None for key in required):
                continue
            table = Table(name, MetaData(), autoload_with=session.get_bind())
            return table, {key: value for key, value in mapping.items() if value is not None}
        return None

    @staticmethod
    def _chunks(items: list[str], size: int):
        for index in range(0, len(items), size):
            yield items[index:index + size]

    def _load_prices(self, session, symbols: list[str], cutoff: date) -> dict[str, list[dict[str, Any]]]:
        resolved = self._resolve_table(session, self.PRICE_TABLES, self.PRICE_ALIASES, {"symbol", "date", "close", "volume"})
        if resolved is None:
            return {}
        table, mapping = resolved
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        columns = [table.c[mapping[key]].label(key) for key in ("symbol", "date", "close", "volume")]
        for batch in self._chunks(symbols, self.policy.batch_size):
            statement = select(*columns).where(
                table.c[mapping["symbol"]].in_(batch),
                table.c[mapping["date"]] >= cutoff,
            ).order_by(table.c[mapping["symbol"]], table.c[mapping["date"]].desc())
            for row in session.execute(statement):
                item = dict(row._mapping)
                grouped[str(item["symbol"]).upper()].append(item)
        return grouped

    def _load_options(self, session, symbols: list[str], cutoff: date) -> dict[str, list[dict[str, Any]]]:
        resolved = self._resolve_table(session, self.OPTION_TABLES, self.OPTION_ALIASES, {"symbol", "quote_date", "volume", "open_interest"})
        if resolved is None:
            return {}
        table, mapping = resolved
        keys = tuple(key for key in ("symbol", "quote_date", "bid", "ask", "volume", "open_interest") if key in mapping)
        columns = [table.c[mapping[key]].label(key) for key in keys]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for batch in self._chunks(symbols, self.policy.batch_size):
            statement = select(*columns).where(
                table.c[mapping["symbol"]].in_(batch),
                table.c[mapping["quote_date"]] >= cutoff,
            )
            for row in session.execute(statement):
                item = dict(row._mapping)
                grouped[str(item["symbol"]).upper()].append(item)
        return grouped

    @staticmethod
    def _float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bool(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "halted"}

    @staticmethod
    def _atomic_write(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
        import io
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def build(
        self,
        *,
        session,
        universe_csv: str | Path,
        output_csv: str | Path = "data/market/liquidity_metrics.csv",
        manifest_json: str | Path = "data/market/liquidity_metrics_manifest.json",
        diagnostics_json: str | Path = "reports/m35/phase1/liquidity_metrics/build_diagnostics.json",
        reference_csv: str | Path | None = None,
        quote_csv: str | Path | None = None,
        as_of: date | None = None,
    ) -> LiquidityMetricsBuildResult:
        generated_at = datetime.now(timezone.utc)
        effective_date = as_of or generated_at.date()
        universe_rows = self._read_csv(universe_csv)
        symbols = self._normalize_symbols(universe_rows)
        if not symbols:
            raise ValueError(f"Universe is empty or missing symbol column: {universe_csv}")

        reference = {str(row.get("symbol") or row.get("ticker") or "").upper(): row for row in self._read_csv(reference_csv)}
        quotes = {str(row.get("symbol") or row.get("ticker") or "").upper(): row for row in self._read_csv(quote_csv)}
        cutoff = effective_date - timedelta(days=self.policy.calendar_lookback_days)
        prices = self._load_prices(session, symbols, cutoff)
        options = self._load_options(session, symbols, cutoff)

        diagnostics: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        missing_price = missing_reference = missing_option = 0
        universe_by_symbol = {str(row.get("symbol") or row.get("ticker") or "").upper(): row for row in universe_rows}

        for symbol in symbols:
            observations = prices.get(symbol, [])[: self.policy.lookback_trading_days]
            valid = [row for row in observations if self._float(row.get("close")) is not None and self._float(row.get("volume")) is not None]
            if len(valid) < self.policy.minimum_price_observations:
                missing_price += 1
                diagnostics.append({"symbol": symbol, "severity": "ERROR", "code": "INSUFFICIENT_PRICE_HISTORY", "observations": len(valid)})
                if self.policy.require_price_history:
                    continue
            latest = valid[0] if valid else {}
            price = self._float(latest.get("close"))
            volumes = [self._float(row.get("volume")) or 0.0 for row in valid]
            dollar_volumes = [(self._float(row.get("close")) or 0.0) * (self._float(row.get("volume")) or 0.0) for row in valid]
            avg_volume = sum(volumes) / len(volumes) if volumes else None
            avg_dollar = sum(dollar_volumes) / len(dollar_volumes) if dollar_volumes else None

            ref = reference.get(symbol, {})
            quote = quotes.get(symbol, {})
            universe = universe_by_symbol.get(symbol, {})
            market_cap = self._float(ref.get("market_cap") or universe.get("market_cap"))
            halted = self._bool(ref.get("halted") or quote.get("halted") or universe.get("halted"))
            if market_cap is None:
                missing_reference += 1
                diagnostics.append({"symbol": symbol, "severity": "WARNING", "code": "MISSING_MARKET_CAP"})

            option_rows = options.get(symbol, [])
            option_volume = option_oi = None
            option_spread = None
            if option_rows:
                latest_option_date = max(row.get("quote_date") for row in option_rows if row.get("quote_date") is not None)
                latest_rows = [row for row in option_rows if row.get("quote_date") == latest_option_date]
                option_volume = int(sum(self._float(row.get("volume")) or 0.0 for row in latest_rows))
                option_oi = int(sum(self._float(row.get("open_interest")) or 0.0 for row in latest_rows))
                spreads = []
                for row in latest_rows:
                    bid, ask = self._float(row.get("bid")), self._float(row.get("ask"))
                    if bid is not None and ask is not None and ask >= bid and (ask + bid) > 0:
                        spreads.append((ask - bid) / ((ask + bid) / 2.0))
                option_spread = sum(spreads) / len(spreads) if spreads else None
            else:
                missing_option += 1
                diagnostics.append({"symbol": symbol, "severity": "INFO", "code": "MISSING_OPTION_SNAPSHOT"})

            spread = self._float(quote.get("bid_ask_spread_pct"))
            if spread is None:
                bid, ask = self._float(quote.get("bid")), self._float(quote.get("ask"))
                if bid is not None and ask is not None and ask >= bid and (ask + bid) > 0:
                    spread = (ask - bid) / ((ask + bid) / 2.0)
            if spread is None:
                spread = option_spread

            as_of_value = latest.get("date") or effective_date
            records.append({
                "symbol": symbol,
                "as_of": as_of_value.isoformat() if hasattr(as_of_value, "isoformat") else str(as_of_value),
                "price": "" if price is None else f"{price:.6f}",
                "average_daily_volume": "" if avg_volume is None else int(round(avg_volume)),
                "average_daily_dollar_volume": "" if avg_dollar is None else f"{avg_dollar:.2f}",
                "bid_ask_spread_pct": "" if spread is None else f"{spread:.8f}",
                "market_cap": "" if market_cap is None else f"{market_cap:.2f}",
                "option_volume": "" if option_volume is None else option_volume,
                "option_open_interest": "" if option_oi is None else option_oi,
                "halted": str(halted).lower(),
            })

        csv_payload = self._csv_text(records, self.OUTPUT_FIELDS)
        digest = hashlib.sha256(csv_payload.encode("utf-8")).hexdigest()
        output_path, manifest_path, diagnostics_path = Path(output_csv), Path(manifest_json), Path(diagnostics_json)
        self._atomic_write(output_path, csv_payload)
        status = "READY" if not missing_price else ("DEGRADED" if records else "FAILED")
        manifest = {
            "schema_version": "m35.phase1.liquidity_metrics.v1",
            "generated_at": generated_at.isoformat(), "as_of": effective_date.isoformat(),
            "status": status, "universe_count": len(symbols), "metrics_count": len(records),
            "missing_price_count": missing_price, "missing_reference_count": missing_reference,
            "missing_option_count": missing_option, "lookback_trading_days": self.policy.lookback_trading_days,
            "sha256": digest, "output_csv": str(output_path),
            "sources": {"price_history": "database", "option_chain": "database", "reference_csv": str(reference_csv or ""), "quote_csv": str(quote_csv or "")},
        }
        self._atomic_write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        self._atomic_write(diagnostics_path, json.dumps({"manifest": manifest, "diagnostics": diagnostics}, indent=2, default=str, sort_keys=True) + "\n")
        return LiquidityMetricsBuildResult(
            generated_at=generated_at, status=status, universe_count=len(symbols), metrics_count=len(records),
            missing_price_count=missing_price, missing_reference_count=missing_reference,
            missing_option_count=missing_option, output_csv=str(output_path), manifest_json=str(manifest_path),
            diagnostics_json=str(diagnostics_path), sha256=digest, diagnostics=tuple(diagnostics),
        )
