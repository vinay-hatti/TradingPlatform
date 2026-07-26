from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from trading_ai.polygon_intelligence import HistoricalVolatilityEngine, MicrostructureLiquidityEngine
from trading_ai.persistence_normalization import strict_json_dumps, to_native


@dataclass
class IngestionPhaseResult:
    name: str
    status: str
    started_at: str
    completed_at: str
    rows_written: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def successful(self) -> bool:
        return self.status in {"READY", "REUSED", "NO_NEW_DATA", "DEGRADED", "SKIPPED"}


@dataclass
class UnifiedIngestionProfile:
    run_id: str
    started_at: str
    completed_at: str
    status: str
    symbols: int
    phases: list[IngestionPhaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "symbols": self.symbols,
            "phases": [asdict(p) for p in self.phases],
        }


class PhaseRunner:
    def __init__(self, *, continue_on_error: bool) -> None:
        self.continue_on_error = continue_on_error
        self.results: list[IngestionPhaseResult] = []

    def run(self, name: str, fn: Callable[[], Mapping[str, Any] | None], *, skipped: bool = False) -> IngestionPhaseResult:
        started = datetime.now(timezone.utc)
        if skipped:
            result = IngestionPhaseResult(name, "SKIPPED", started.isoformat(), datetime.now(timezone.utc).isoformat())
            self.results.append(result)
            return result
        try:
            payload = dict(fn() or {})
            status = str(payload.pop("status", "READY"))
            rows = int(payload.pop("rows_written", 0) or 0)
            result = IngestionPhaseResult(name, status, started.isoformat(), datetime.now(timezone.utc).isoformat(), rows, payload)
        except Exception as exc:
            result = IngestionPhaseResult(name, "FAILED", started.isoformat(), datetime.now(timezone.utc).isoformat(), error=f"{type(exc).__name__}: {exc}")
            self.results.append(result)
            if not self.continue_on_error:
                raise
            return result
        self.results.append(result)
        return result


class PolygonDerivedSnapshotPublisher:
    """Publishes compatibility option rows into timestamped Milestone 46 tables.

    Polygon remains authoritative. The legacy option_contract_history table is retained
    as a compatibility sink for existing scanners, while these tables preserve capture
    identity and support historical analytics/replay.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def publish_option_snapshot(
        self,
        *,
        symbols: Sequence[str],
        capture_date: date,
        snapshot_timestamp: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        ts = snapshot_timestamp or datetime.now(timezone.utc)
        sid = snapshot_id or f"polygon-{ts.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
        symbol_list = sorted({s.strip().upper() for s in symbols if s and s.strip()})
        rows = self.session.execute(
            text(
                """
                SELECT underlying_symbol, option_symbol, expiry, option_type, strike,
                       bid, ask, mid, last, volume, open_interest, implied_volatility,
                       delta, gamma, theta, vega
                  FROM option_contract_history
                 WHERE quote_date = :capture_date
                   AND underlying_symbol = ANY(:symbols)
                """
            ),
            {"capture_date": capture_date, "symbols": symbol_list},
        ).mappings().all()
        by_symbol = {str(r["underlying_symbol"]).upper() for r in rows}
        completeness = (len(by_symbol) / len(symbol_list) * 100.0) if symbol_list else 0.0
        is_partial = len(by_symbol) < len(symbol_list)
        status = "PARTIAL" if is_partial else "READY"
        run_id = self.session.execute(
            text(
                """
                INSERT INTO option_snapshot_run
                    (snapshot_id, snapshot_timestamp, as_of_date, provider, capture_status,
                     is_partial, completeness_score, symbols_requested, symbols_succeeded,
                     symbols_failed, contracts_received, contracts_persisted, warnings_json)
                VALUES
                    (:sid, :ts, :as_of, 'POLYGON', :status, :partial, :score, :requested,
                     :succeeded, :failed, :received, 0, :warnings)
                RETURNING id
                """
            ),
            {
                "sid": sid,
                "ts": ts,
                "as_of": capture_date,
                "status": status,
                "partial": is_partial,
                "score": completeness,
                "requested": len(symbol_list),
                "succeeded": len(by_symbol),
                "failed": max(0, len(symbol_list) - len(by_symbol)),
                "received": len(rows),
                "warnings": strict_json_dumps([] if not is_partial else ["SOME_SYMBOLS_HAVE_NO_OPTION_ROWS"]),
            },
        ).scalar_one()
        written = 0
        for r in rows:
            bid, ask = r["bid"], r["ask"]
            quality = "COMPLETE_QUOTE" if (bid or 0) > 0 and (ask or 0) > 0 else "ONE_SIDED_QUOTE" if (bid or 0) > 0 or (ask or 0) > 0 else "NO_QUOTE"
            mark = r["mid"] if r["mid"] is not None else ((bid + ask) / 2 if bid is not None and ask is not None else r["last"])
            self.session.execute(
                text(
                    """
                    INSERT INTO option_contract_snapshot
                        (snapshot_run_id, snapshot_timestamp, underlying_symbol, option_symbol,
                         expiry, option_type, strike, bid, ask, last, mark, volume, open_interest,
                         implied_volatility, delta, gamma, theta, vega, quote_quality, provider)
                    VALUES
                        (:run_id, :ts, :underlying, :option_symbol, :expiry, :option_type, :strike,
                         :bid, :ask, :last, :mark, :volume, :oi, :iv, :delta, :gamma, :theta, :vega,
                         :quality, 'POLYGON')
                    ON CONFLICT (snapshot_run_id, option_symbol) DO NOTHING
                    """
                ),
                {
                    "run_id": run_id, "ts": ts, "underlying": r["underlying_symbol"],
                    "option_symbol": r["option_symbol"], "expiry": r["expiry"], "option_type": r["option_type"],
                    "strike": r["strike"], "bid": bid, "ask": ask, "last": r["last"], "mark": mark,
                    "volume": r["volume"], "oi": r["open_interest"], "iv": r["implied_volatility"],
                    "delta": r["delta"], "gamma": r["gamma"], "theta": r["theta"], "vega": r["vega"],
                    "quality": quality,
                },
            )
            written += 1
        self.session.execute(text("UPDATE option_snapshot_run SET contracts_persisted=:n WHERE id=:id"), {"n": written, "id": run_id})
        self.session.commit()
        return {"status": "DEGRADED" if is_partial else "READY", "rows_written": written, "snapshot_id": sid, "snapshot_timestamp": ts.isoformat(), "completeness_score": round(completeness, 4)}

    def build_volatility_snapshots(self, *, snapshot_id: str, capture_date: date) -> dict[str, Any]:
        run = self.session.execute(text("SELECT id, snapshot_timestamp FROM option_snapshot_run WHERE snapshot_id=:sid AND provider='POLYGON'"), {"sid": snapshot_id}).mappings().one()
        rows = self.session.execute(
            text(
                """
                SELECT underlying_symbol, expiry, strike, option_type, implied_volatility,
                       delta, bid, ask, open_interest
                  FROM option_contract_snapshot
                 WHERE snapshot_run_id=:run_id
                """
            ), {"run_id": run["id"]}
        ).mappings().all()
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for r in rows: grouped.setdefault(str(r["underlying_symbol"]), []).append(r)
        written = 0
        for symbol, contracts in grouped.items():
            liquid = [r for r in contracts if (r["implied_volatility"] or 0) > 0 and (r["bid"] or 0) > 0 and (r["ask"] or 0) >= (r["bid"] or 0)]
            near = sorted(liquid, key=lambda r: (abs((r["expiry"] - capture_date).days - 30), abs(abs(float(r["delta"] or 0.5)) - 0.5)))[:12]
            atm_iv = mean(float(r["implied_volatility"]) for r in near) if near else None
            history = [float(x) for x in self.session.execute(text("SELECT atm_iv_30d FROM underlying_volatility_snapshot WHERE underlying_symbol=:s AND atm_iv_30d IS NOT NULL AND snapshot_timestamp < :ts ORDER BY snapshot_timestamp DESC LIMIT 252"), {"s": symbol, "ts": run["snapshot_timestamp"]}).scalars().all()]
            rank = HistoricalVolatilityEngine.iv_rank(atm_iv, history) if atm_iv is not None else {"value": None, "observation_count": len(history), "confidence": 0, "status": "NO_CURRENT_IV"}
            pct = HistoricalVolatilityEngine.iv_percentile(atm_iv, history) if atm_iv is not None else {"value": None, "observation_count": len(history), "confidence": 0, "status": "NO_CURRENT_IV"}
            closes = self.session.execute(text("SELECT close FROM price_history WHERE symbol=:s AND date <= :d ORDER BY date DESC LIMIT 21"), {"s": symbol, "d": capture_date}).scalars().all()
            returns = [math.log(float(closes[i-1]) / float(closes[i])) for i in range(1, len(closes)) if closes[i] and closes[i-1] and float(closes[i]) > 0 and float(closes[i-1]) > 0]
            rv = HistoricalVolatilityEngine.realized_volatility(returns)
            vrp = (atm_iv - rv) if atm_iv is not None and rv is not None else None
            confidence = min(float(rank.get("confidence") or 0), float(pct.get("confidence") or 0))
            fit = HistoricalVolatilityEngine.strategy_fit(rank.get("value"), pct.get("value"), vrp)
            payload = {"iv_rank_status": rank.get("status"), "iv_percentile_status": pct.get("status"), "contracts_used": len(near), "history_observations": len(history)}
            payload = to_native(payload)
            self.session.execute(text("""
                INSERT INTO underlying_volatility_snapshot
                    (snapshot_timestamp, underlying_symbol, as_of_date, atm_iv_30d, realized_vol_20d,
                     iv_rank_252d, iv_percentile_252d, volatility_risk_premium, strategy_fit,
                     observation_count, confidence, provenance, payload_json)
                VALUES (:ts,:s,:d,:iv,:rv,:rank,:pct,:vrp,:fit,:obs,:conf,'POLYGON_OPTION_SNAPSHOTS',:payload)
                ON CONFLICT (snapshot_timestamp, underlying_symbol) DO UPDATE SET
                    atm_iv_30d=EXCLUDED.atm_iv_30d, realized_vol_20d=EXCLUDED.realized_vol_20d,
                    iv_rank_252d=EXCLUDED.iv_rank_252d, iv_percentile_252d=EXCLUDED.iv_percentile_252d,
                    volatility_risk_premium=EXCLUDED.volatility_risk_premium, strategy_fit=EXCLUDED.strategy_fit,
                    observation_count=EXCLUDED.observation_count, confidence=EXCLUDED.confidence, payload_json=EXCLUDED.payload_json
            """), {"ts": run["snapshot_timestamp"], "s": symbol, "d": capture_date, "iv": atm_iv, "rv": rv, "rank": rank.get("value"), "pct": pct.get("value"), "vrp": vrp, "fit": fit, "obs": len(history), "conf": confidence, "payload": strict_json_dumps(payload)})
            written += 1
        self.session.commit()
        return {"status": "READY" if written else "DEGRADED", "rows_written": written, "symbols_evaluated": len(grouped)}

    def build_liquidity_snapshots(self, *, snapshot_id: str, capture_date: date) -> dict[str, Any]:
        run = self.session.execute(text("SELECT id, snapshot_timestamp FROM option_snapshot_run WHERE snapshot_id=:sid AND provider='POLYGON'"), {"sid": snapshot_id}).mappings().one()
        rows = self.session.execute(text("SELECT underlying_symbol, bid, ask, volume FROM option_contract_snapshot WHERE snapshot_run_id=:id"), {"id": run["id"]}).mappings().all()
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for r in rows: grouped.setdefault(str(r["underlying_symbol"]), []).append(r)
        written = 0
        for symbol, contracts in grouped.items():
            quotes = [{"bid": r["bid"], "ask": r["ask"]} for r in contracts]
            metrics = to_native(MicrostructureLiquidityEngine.snapshot_metrics(quotes, ()))
            confidence = min(100.0, metrics["executable_quote_pct"])
            self.session.execute(text("""
                INSERT INTO microstructure_liquidity_snapshot
                    (snapshot_timestamp, symbol, as_of_date, executable_quote_pct,
                     median_relative_spread_pct, average_trade_size, liquidity_score,
                     liquidity_regime, depth_available, confidence, provenance, payload_json)
                VALUES (:ts,:s,:d,:coverage,:spread,NULL,:score,:regime,false,:conf,'POLYGON_OPTION_NBBO_SNAPSHOT',:payload)
                ON CONFLICT (snapshot_timestamp, symbol) DO UPDATE SET
                    executable_quote_pct=EXCLUDED.executable_quote_pct,
                    median_relative_spread_pct=EXCLUDED.median_relative_spread_pct,
                    liquidity_score=EXCLUDED.liquidity_score, liquidity_regime=EXCLUDED.liquidity_regime,
                    confidence=EXCLUDED.confidence, payload_json=EXCLUDED.payload_json
            """), {"ts": run["snapshot_timestamp"], "s": symbol, "d": capture_date, "coverage": metrics["executable_quote_pct"], "spread": metrics["median_relative_spread_pct"], "score": metrics["liquidity_score"], "regime": metrics["liquidity_regime"], "conf": confidence, "payload": strict_json_dumps(metrics)})
            written += 1
        self.session.commit()
        return {"status": "READY" if written else "DEGRADED", "rows_written": written, "symbols_evaluated": len(grouped), "depth_status": "CAPABILITY_UNAVAILABLE", "trade_metrics_status": "NOT_CAPTURED_BY_SNAPSHOT_ENDPOINT"}


def write_unified_profile(profile: UnifiedIngestionProfile, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(strict_json_dumps(profile.to_dict(), indent=2, default=str), encoding="utf-8")
