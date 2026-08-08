from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from math import sqrt, log
from uuid import uuid4

from sqlalchemy import MetaData, Table, func, inspect, select

from trading_ai.broker.ibkr.database_models import BrokerAccountSnapshotModel
from trading_ai.broker_portfolio_sync.models import (
    BrokerCurrentPositionModel,
    BrokerPortfolioPublicationModel,
)
from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.market_intelligence.database_models import (
    SectorMembershipModel,
    SymbolReturnSnapshotModel,
)
from trading_ai.portfolio_management.database_models import PortfolioPositionModel

from .models import (
    PortfolioFitAssessmentModel,
    PortfolioRiskSnapshotModel,
    PortfolioStressSnapshotModel,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def number(value, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class PortfolioRiskAllocationService:
    """Portfolio-level option risk, exposure, stress, and allocation analytics.

    Exact Polygon option quotes are preferred. Missing enrichment is retained as
    an explicit data-quality warning and receives conservative risk fallbacks.
    """

    POLICY_VERSION = "M64-PORTFOLIO-RISK-1.2"

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def build(self, portfolio_id: str = "PAPER-PRIMARY", actor: str = "m64-risk-engine"):
        with self.session_factory() as session:
            broker_positions = list(
                session.scalars(
                    select(BrokerCurrentPositionModel).where(
                        BrokerCurrentPositionModel.portfolio_id == portfolio_id,
                        BrokerCurrentPositionModel.active.is_(True),
                    )
                ).all()
            )
            local_positions = list(
                session.scalars(
                    select(PortfolioPositionModel).where(
                        PortfolioPositionModel.portfolio_id == portfolio_id,
                        PortfolioPositionModel.status == "OPEN",
                    )
                ).all()
            )
            local_by_id = {row.position_id: row for row in local_positions}
            account = session.scalar(
                select(BrokerAccountSnapshotModel)
                .where(BrokerAccountSnapshotModel.portfolio_id == portfolio_id)
                .order_by(BrokerAccountSnapshotModel.captured_at.desc())
                .limit(1)
            )
            publication = session.scalar(
                select(BrokerPortfolioPublicationModel)
                .where(BrokerPortfolioPublicationModel.portfolio_id == portfolio_id)
                .order_by(BrokerPortfolioPublicationModel.published_at.desc())
                .limit(1)
            )

            net_liquidation = number(getattr(account, "net_liquidation", 0))
            buying_power = number(getattr(account, "buying_power", 0))
            greeks = defaultdict(float)
            beta_weighted_delta = 0.0
            exposures = {
                key: defaultdict(float)
                for key in (
                    "symbol",
                    "sector",
                    "industry",
                    "theme",
                    "strategy",
                    "asset_class",
                    "currency",
                    "dte_bucket",
                )
            }
            capital_committed = open_risk = market_value = 0.0
            position_rows: list[dict] = []
            warnings: list[str] = []
            exact_quotes = 0
            exact_classifications = 0
            timestamp = datetime.now(timezone.utc)

            for broker in broker_positions:
                local = local_by_id.get(broker.portfolio_position_id or "")
                enrichment = self._enrich_position(session, broker, local, timestamp)
                if enrichment["quote_quality"] == "EXACT_POLYGON":
                    exact_quotes += 1
                else:
                    warnings.append(
                        f"{broker.symbol}:{broker.contract_id}: {enrichment['quote_quality']}"
                    )
                if enrichment["classification_quality"] == "GOVERNED":
                    exact_classifications += 1

                signed_quantity = number(broker.signed_quantity)
                multiplier = max(1.0, number(broker.multiplier, 1.0))
                abs_quantity = abs(signed_quantity)
                position_market_value = abs(enrichment["option_mark"] * multiplier * signed_quantity)
                if position_market_value <= 0:
                    position_market_value = abs(number(broker.market_value))
                position_capital = self._capital_committed(
                    broker, local, enrichment, abs_quantity, multiplier
                )
                maximum_loss = self._maximum_loss(
                    broker, local, enrichment, position_capital
                )
                market_value += position_market_value
                capital_committed += position_capital
                open_risk += maximum_loss

                position_greeks = {}
                for greek_name in ("delta", "gamma", "theta", "vega", "rho"):
                    unit_value = number(enrichment.get(greek_name))
                    aggregate_value = unit_value * signed_quantity * multiplier
                    greeks[greek_name] += aggregate_value
                    position_greeks[greek_name] = aggregate_value

                underlying_equivalent = (
                    position_greeks["delta"] * enrichment["underlying_price"]
                )
                beta_weighted_delta += underlying_equivalent * enrichment["beta"]

                labels = {
                    "symbol": broker.symbol,
                    "sector": enrichment["sector"],
                    "industry": enrichment["industry"],
                    "theme": enrichment["theme"],
                    "strategy": enrichment["strategy"],
                    "asset_class": broker.security_type,
                    "currency": broker.currency,
                    "dte_bucket": enrichment["dte_bucket"],
                }
                for dimension, label in labels.items():
                    exposures[dimension][label] += position_market_value

                position_rows.append(
                    {
                        "symbol": broker.symbol,
                        "contract_id": broker.contract_id,
                        "option_symbol": enrichment["option_symbol"],
                        "market_value": position_market_value,
                        "capital_committed": position_capital,
                        "maximum_loss": maximum_loss,
                        "strategy": enrichment["strategy"],
                        "sector": enrichment["sector"],
                        "industry": enrichment["industry"],
                        "theme": enrichment["theme"],
                        "lineage": enrichment["lineage"],
                        "security_type": broker.security_type,
                        "quantity": signed_quantity,
                        "multiplier": multiplier,
                        "expiry": broker.expiry,
                        "strike": broker.strike,
                        "right": broker.right,
                        "option_mark": enrichment["option_mark"],
                        "underlying_price": enrichment["underlying_price"],
                        "implied_volatility": enrichment["implied_volatility"],
                        "realized_volatility_20d": enrichment["realized_volatility_20d"],
                        "beta": enrichment["beta"],
                        "greeks": position_greeks,
                        "quote_quality": enrichment["quote_quality"],
                        "classification_quality": enrichment["classification_quality"],
                        "risk_method": enrichment["risk_method"],
                    }
                )

            structures = self._reconstruct_structures(position_rows)
            self._apply_structure_classification(position_rows, structures)
            # Rebuild strategy exposure after multi-leg reconstruction.
            exposures["strategy"] = defaultdict(float)
            for row in position_rows:
                exposures["strategy"][row["strategy"]] += row["market_value"]
            exact_classifications = sum(
                1 for row in position_rows
                if row["classification_quality"] in {"GOVERNED", "RECONSTRUCTED_MULTI_LEG"}
            )

            weights = [
                value / market_value for value in exposures["symbol"].values()
            ] if market_value else []
            hhi = sum(weight * weight for weight in weights)
            concentration = clamp(hhi * 100)
            diversification = clamp(100 - concentration)
            var95, expected_shortfall = self._delta_gamma_vega_var(position_rows)
            heat_pct = (open_risk / net_liquidation * 100) if net_liquidation else 0.0
            usage_pct = (
                capital_committed / net_liquidation * 100
            ) if net_liquidation else 0.0
            enrichment_coverage = (
                exact_quotes / len(broker_positions) * 100 if broker_positions else 0.0
            )
            classification_coverage = (
                exact_classifications / len(broker_positions) * 100
                if broker_positions else 0.0
            )
            health = clamp(
                100
                - max(0, heat_pct - 10) * 2
                - concentration * 0.25
                - max(0, usage_pct - 50) * 0.5
                - max(0, 100 - enrichment_coverage) * 0.15
            )
            stress = self._stress_payload(position_rows, market_value)
            status = (
                "READY"
                if broker_positions and enrichment_coverage == 100
                else "DEGRADED"
            )
            payload = {
                "policy_version": self.POLICY_VERSION,
                "generated_by": actor,
                "position_count": len(broker_positions),
                "greeks": {
                    **dict(greeks),
                    "beta_weighted_delta": beta_weighted_delta,
                },
                "exposures": {
                    key: dict(value) for key, value in exposures.items()
                },
                "capital": {
                    "net_liquidation": net_liquidation,
                    "buying_power": buying_power,
                    "market_value": market_value,
                    "capital_committed": capital_committed,
                    "capital_usage_pct": usage_pct,
                    "open_risk": open_risk,
                    "portfolio_heat_pct": heat_pct,
                },
                "risk": {
                    "var_95_one_day": var95,
                    "expected_shortfall_95_one_day": expected_shortfall,
                    "methodology": "DELTA_GAMMA_VEGA_1D_PROXY",
                    "concentration_hhi": hhi,
                    "concentration_score": concentration,
                    "diversification_score": diversification,
                    "stress": stress,
                },
                "data_quality": {
                    "exact_option_quote_coverage_pct": enrichment_coverage,
                    "governed_classification_coverage_pct": classification_coverage,
                    "warnings": warnings,
                    "structure_count": len(structures),
                    "multi_leg_position_count": sum(len(item["leg_indexes"]) for item in structures),
                },
                "structures": structures,
                "positions": position_rows,
                "limits": {
                    "max_symbol_pct": 10,
                    "max_sector_pct": 25,
                    "max_strategy_pct": 35,
                    "max_portfolio_heat_pct": 20,
                    "risk_per_trade_pct": 2,
                },
            }
            snapshot = PortfolioRiskSnapshotModel(
                snapshot_id="M64-RISK-" + uuid4().hex.upper(),
                portfolio_id=portfolio_id,
                snapshot_timestamp=now(),
                broker_publication_id=getattr(publication, "publication_id", None),
                status=status,
                health_score=health,
                net_liquidation=net_liquidation,
                buying_power=buying_power,
                capital_committed=capital_committed,
                open_risk=open_risk,
                var_95=var95,
                expected_shortfall_95=expected_shortfall,
                portfolio_heat_pct=heat_pct,
                concentration_score=concentration,
                diversification_score=diversification,
                payload_json=payload,
            )
            session.add(snapshot)
            session.commit()
            return self.serialize(snapshot)

    def _enrich_position(self, session, broker, local, timestamp: datetime) -> dict:
        expiry_date = None
        try:
            expiry_date = date.fromisoformat(str(broker.expiry)[:10]) if broker.expiry else None
        except ValueError:
            pass
        option_type = "CALL" if str(broker.right).upper().startswith("C") else "PUT"
        quote = None
        if expiry_date and broker.strike is not None:
            chain = OptionChainRepository(session).get_latest_snapshot(
                broker.symbol, timestamp.date()
            )
            target_strike = number(broker.strike)
            for candidate in chain:
                candidate_type = str(candidate.get("option_type") or "").upper()
                candidate_expiry = candidate.get("expiry")
                if hasattr(candidate_expiry, "isoformat"):
                    candidate_expiry = candidate_expiry.isoformat()
                if (
                    candidate_type in {option_type, option_type[0]}
                    and str(candidate_expiry)[:10] == expiry_date.isoformat()
                    and abs(number(candidate.get("strike")) - target_strike) < 1e-6
                ):
                    quote = candidate
                    break
        membership = session.scalar(
            select(SectorMembershipModel)
            .where(
                func.upper(SectorMembershipModel.symbol) == broker.symbol.upper(),
                SectorMembershipModel.is_active.is_(True),
            )
            .order_by(SectorMembershipModel.effective_from.desc())
            .limit(1)
        )
        returns = session.scalar(
            select(SymbolReturnSnapshotModel)
            .where(func.upper(SymbolReturnSnapshotModel.symbol) == broker.symbol.upper())
            .order_by(SymbolReturnSnapshotModel.snapshot_timestamp.desc())
            .limit(1)
        )
        latest_underlying_price = 0.0
        computed_rv = 0.0
        computed_beta = 0.0
        inspector = inspect(session.get_bind())
        if "price_history" in inspector.get_table_names():
            price_table = Table("price_history", MetaData(), autoload_with=session.get_bind())
            latest_underlying_price = number(session.execute(
                select(price_table.c.close)
                .where(func.upper(price_table.c.symbol) == broker.symbol.upper())
                .order_by(price_table.c.date.desc())
                .limit(1)
            ).scalar_one_or_none())
            computed_rv, computed_beta = self._market_metrics(
                session, price_table, broker.symbol.upper(), "SPY"
            )

        local_strategy = str(getattr(local, "strategy_type", "") or "")
        metadata = dict(getattr(local, "metadata_json", {}) or {})
        lineage_keys = (
            "decision_snapshot_id", "decision_state_hash", "trade_plan_id",
            "execution_intent_id", "opportunity_id", "management_snapshot_id",
        )
        lineage = {key: metadata.get(key) for key in lineage_keys if metadata.get(key)}
        source_artifact = str(getattr(local, "source_artifact", "") or "")
        governed_lineage = bool(lineage) or "M62" in source_artifact.upper() or str(getattr(broker, "provenance", "")).upper() == "INSTITUTIONAL_OPTIONS"
        generic = {"", "BROKER_SYNCED_OPTION", "BROKER_POSITION", "UNKNOWN"}
        if local_strategy not in generic:
            strategy = local_strategy
            classification_quality = "GOVERNED" if governed_lineage else "GOVERNED_LOCAL_STRATEGY"
        else:
            side = "LONG" if number(broker.signed_quantity) > 0 else "SHORT"
            strategy = f"{side}_{option_type}"
            classification_quality = "GOVERNED" if governed_lineage else "INFERRED_SINGLE_LEG"

        option_mark = 0.0
        quote_quality = "BROKER_FALLBACK"
        if quote is not None:
            bid = number(quote.get("bid"))
            ask = number(quote.get("ask"))
            option_mark = number(quote.get("mid")) or ((bid + ask) / 2 if bid > 0 and ask >= bid else 0)
            option_mark = option_mark or number(quote.get("last"))
            quote_quality = "EXACT_POLYGON"
        if option_mark <= 0:
            broker_market = number(broker.market_price)
            multiplier = max(1.0, number(broker.multiplier, 1.0))
            option_mark = broker_market / multiplier if broker_market > 20 else broker_market
            option_mark = option_mark or number(broker.average_cost) / multiplier

        expiry_days = (expiry_date - timestamp.date()).days if expiry_date else 0
        dte_bucket = (
            "0-7" if expiry_days <= 7 else
            "8-30" if expiry_days <= 30 else
            "31-60" if expiry_days <= 60 else
            "61-120" if expiry_days <= 120 else "121+"
        )
        return {
            "option_symbol": str((quote or {}).get("contract_ticker") or broker.local_symbol or ""),
            "option_mark": option_mark,
            "underlying_price": latest_underlying_price,
            "implied_volatility": number((quote or {}).get("implied_volatility")),
            "realized_volatility_20d": number(getattr(returns, "realized_volatility_20d", 0)) or computed_rv,
            "beta": number(getattr(returns, "beta_60d", 0)) or computed_beta or 1.0,
            "delta": number((quote or {}).get("delta")),
            "gamma": number((quote or {}).get("gamma")),
            "theta": number((quote or {}).get("theta")),
            "vega": number((quote or {}).get("vega")),
            "rho": number((quote or {}).get("rho")),
            "sector": str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN"),
            "industry": self._industry_label(
                broker.symbol,
                str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN"),
                str(getattr(membership, "industry", "UNKNOWN") or "UNKNOWN"),
            ),
            "theme": self._theme_label(broker.symbol, str(getattr(membership, "sector", "UNKNOWN") or "UNKNOWN")),
            "lineage": lineage,
            "strategy": strategy,
            "classification_quality": classification_quality,
            "quote_quality": quote_quality,
            "dte_bucket": dte_bucket,
            "risk_method": "LONG_PREMIUM" if number(broker.signed_quantity) > 0 else "SHORT_OPTION_CONSERVATIVE",
        }

    def _capital_committed(self, broker, local, enrichment, quantity, multiplier) -> float:
        local_value = number(getattr(local, "capital_committed", 0))
        if local_value > 0 and str(getattr(local, "strategy_type", "")) not in {
            "BROKER_SYNCED_OPTION", "BROKER_POSITION", "UNKNOWN", ""
        }:
            return local_value
        average_cost = abs(number(broker.average_cost))
        # IBKR option averageCost is commonly already expressed per contract.
        if broker.security_type == "OPT" and average_cost > enrichment["option_mark"] * 10:
            return average_cost * quantity
        return max(0.0, average_cost * quantity * multiplier)

    def _maximum_loss(self, broker, local, enrichment, committed) -> float:
        local_loss = number(getattr(local, "maximum_loss", 0))
        if local_loss > 0 and enrichment["classification_quality"] == "GOVERNED":
            return local_loss
        if number(broker.signed_quantity) > 0:
            return committed
        underlying = enrichment["underlying_price"]
        if enrichment["strategy"] == "SHORT_PUT" and underlying > 0:
            return max(committed, number(broker.strike) * max(1.0, number(broker.multiplier)) * abs(number(broker.signed_quantity)))
        return max(committed, underlying * max(1.0, number(broker.multiplier)) * abs(number(broker.signed_quantity)))

    def _delta_gamma_vega_var(self, rows: list[dict]) -> tuple[float, float]:
        variance = 0.0
        convexity_buffer = 0.0
        volatility_buffer = 0.0
        for row in rows:
            rv = row["realized_volatility_20d"] or row["implied_volatility"] or 0.30
            daily_vol = max(0.005, rv / sqrt(252))
            underlying = row["underlying_price"] or max(1.0, row["market_value"])
            delta_exposure = row["greeks"]["delta"] * underlying
            variance += (delta_exposure * daily_vol) ** 2
            convexity_buffer += abs(row["greeks"]["gamma"]) * (underlying * daily_vol) ** 2 * 0.5
            volatility_buffer += abs(row["greeks"]["vega"]) * max(0.01, row["implied_volatility"] * 0.10)
        sigma = sqrt(variance) + convexity_buffer + volatility_buffer
        return 1.65 * sigma, 2.06 * sigma

    def _stress_payload(self, rows: list[dict], market_value: float) -> dict:
        def scenario(price_shock: float = 0.0, iv_shock: float = 0.0, sector: str | None = None, spread_cost: float = 0.0):
            pnl = 0.0
            for row in rows:
                if sector and row["sector"].upper() != sector.upper():
                    continue
                spot = row["underlying_price"] or 0.0
                move = spot * price_shock
                pnl += row["greeks"]["delta"] * move
                pnl += 0.5 * row["greeks"]["gamma"] * move * move
                pnl += row["greeks"]["vega"] * iv_shock
                pnl -= row["market_value"] * spread_cost
            return {"estimated_pnl": pnl}

        scenarios = {
            "SPY_DOWN_5": scenario(price_shock=-0.05),
            "TECH_DOWN_10": scenario(price_shock=-0.10, sector="INFORMATION TECHNOLOGY"),
            "FINANCIALS_DOWN_8": scenario(price_shock=-0.08, sector="FINANCIALS"),
            "ENERGY_DOWN_10": scenario(price_shock=-0.10, sector="ENERGY"),
            "CONSUMER_STAPLES_DOWN_5": scenario(price_shock=-0.05, sector="CONSUMER STAPLES"),
            "VIX_UP_20": scenario(iv_shock=0.20),
            "VOLATILITY_CRUSH_15": scenario(iv_shock=-0.15),
            "RATES_UP_1": {
                "estimated_pnl": sum(row["greeks"]["rho"] * 0.01 for row in rows)
            },
            "LIQUIDITY_SHOCK": scenario(spread_cost=0.05),
            "CORRELATION_BREAKDOWN": scenario(price_shock=-0.04, iv_shock=0.10, spread_cost=0.03),
            "DEALER_UNWIND": scenario(price_shock=-0.06, iv_shock=0.12),
            "JOINT_EQUITY_IV_SHOCK": scenario(price_shock=-0.07, iv_shock=0.15),
        }
        return scenarios

    def _market_metrics(self, session, price_table, symbol: str, benchmark: str) -> tuple[float, float]:
        def closes(ticker: str, limit: int = 70) -> list[float]:
            rows = session.execute(
                select(price_table.c.close)
                .where(func.upper(price_table.c.symbol) == ticker)
                .order_by(price_table.c.date.desc())
                .limit(limit)
            ).scalars().all()
            return [number(value) for value in reversed(rows) if number(value) > 0]

        asset = closes(symbol)
        bench = closes(benchmark)
        asset_returns = [log(asset[i] / asset[i - 1]) for i in range(1, len(asset)) if asset[i - 1] > 0]
        rv_window = asset_returns[-20:]
        rv = sqrt(252) * sqrt(sum((x - sum(rv_window) / len(rv_window)) ** 2 for x in rv_window) / max(1, len(rv_window) - 1)) if len(rv_window) >= 2 else 0.0
        count = min(len(asset), len(bench), 61)
        beta = 0.0
        if count >= 21:
            ar = [log(asset[-count + i] / asset[-count + i - 1]) for i in range(1, count)]
            br = [log(bench[-count + i] / bench[-count + i - 1]) for i in range(1, count)]
            am, bm = sum(ar) / len(ar), sum(br) / len(br)
            covariance = sum((a - am) * (b - bm) for a, b in zip(ar, br)) / max(1, len(ar) - 1)
            variance = sum((b - bm) ** 2 for b in br) / max(1, len(br) - 1)
            beta = covariance / variance if variance > 1e-12 else 0.0
        return rv, beta

    def _industry_label(self, symbol: str, sector: str, industry: str) -> str:
        if industry and industry.upper() != "UNKNOWN":
            return industry
        overrides = {
            "WFC": "Diversified Banks", "XOM": "Integrated Oil & Gas",
            "KO": "Beverages", "USO": "Commodity ETF - Crude Oil",
        }
        if symbol.upper() in overrides:
            return overrides[symbol.upper()]
        sector_defaults = {
            "FINANCIALS": "Financial Services", "ENERGY": "Energy",
            "CONSUMER STAPLES": "Consumer Staples", "CRUDE OIL": "Commodity ETF",
            "INFORMATION TECHNOLOGY": "Technology",
        }
        return sector_defaults.get(sector.upper(), "UNKNOWN")

    def _theme_label(self, symbol: str, sector: str) -> str:
        overrides = {"USO": "Crude Oil", "XOM": "Energy", "WFC": "US Banks", "KO": "Defensive Consumer"}
        return overrides.get(symbol.upper(), sector if sector.upper() != "UNKNOWN" else "UNCLASSIFIED")

    def _reconstruct_structures(self, rows: list[dict]) -> list[dict]:
        groups: dict[tuple, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            groups[(row["symbol"], row["expiry"], row["right"])].append(index)
        structures: list[dict] = []
        used: set[int] = set()
        for (symbol, expiry, right), indexes in groups.items():
            longs = sorted([i for i in indexes if rows[i]["quantity"] > 0], key=lambda i: number(rows[i]["strike"]))
            shorts = sorted([i for i in indexes if rows[i]["quantity"] < 0], key=lambda i: number(rows[i]["strike"]))
            for long_i in longs:
                if long_i in used:
                    continue
                match = next((i for i in shorts if i not in used and abs(abs(rows[i]["quantity"]) - abs(rows[long_i]["quantity"])) < 1e-9), None)
                if match is None:
                    continue
                long_strike, short_strike = number(rows[long_i]["strike"]), number(rows[match]["strike"])
                if right == "C":
                    strategy = "BULL_CALL_SPREAD" if long_strike < short_strike else "BEAR_CALL_SPREAD"
                else:
                    strategy = "BEAR_PUT_SPREAD" if long_strike > short_strike else "BULL_PUT_SPREAD"
                multiplier = max(number(rows[long_i]["multiplier"], 100), number(rows[match]["multiplier"], 100))
                quantity = min(abs(rows[long_i]["quantity"]), abs(rows[match]["quantity"]))
                width = abs(short_strike - long_strike) * multiplier * quantity
                net_market_value = rows[long_i]["market_value"] - rows[match]["market_value"]
                net_capital = max(0.0, rows[long_i]["capital_committed"] - rows[match]["capital_committed"])
                maximum_loss = net_capital if strategy in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"} else max(0.0, width - abs(net_capital))
                maximum_profit = max(0.0, width - maximum_loss)
                structure_id = f"{symbol}:{expiry}:{right}:{long_strike:g}-{short_strike:g}"
                structures.append({
                    "structure_id": structure_id, "symbol": symbol, "expiry": expiry,
                    "strategy": strategy, "leg_indexes": [long_i, match],
                    "net_market_value": net_market_value, "capital_committed": net_capital,
                    "maximum_loss": maximum_loss, "maximum_profit": maximum_profit,
                    "width": width, "classification_quality": "RECONSTRUCTED_MULTI_LEG",
                })
                used.update({long_i, match})
        return structures

    def _apply_structure_classification(self, rows: list[dict], structures: list[dict]) -> None:
        for structure in structures:
            for index in structure["leg_indexes"]:
                rows[index]["strategy"] = structure["strategy"]
                rows[index]["classification_quality"] = "RECONSTRUCTED_MULTI_LEG"
                rows[index]["structure_id"] = structure["structure_id"]
                rows[index]["structure_maximum_loss"] = structure["maximum_loss"]
                rows[index]["structure_maximum_profit"] = structure["maximum_profit"]

    def current(self, portfolio_id="PAPER-PRIMARY"):
        with self.session_factory() as session:
            row = session.scalar(
                select(PortfolioRiskSnapshotModel)
                .where(PortfolioRiskSnapshotModel.portfolio_id == portfolio_id)
                .order_by(PortfolioRiskSnapshotModel.snapshot_timestamp.desc())
                .limit(1)
            )
            return None if row is None else self.serialize(row)

    def assess(self, candidate, portfolio_id="PAPER-PRIMARY"):
        snapshot = self.current(portfolio_id) or self.build(portfolio_id)
        payload = snapshot["payload_json"]
        net_liquidation = number(snapshot["net_liquidation"])
        symbol = str(candidate.get("symbol", "UNKNOWN"))
        sector = str(candidate.get("sector", "UNKNOWN"))
        strategy = str(candidate.get("strategy", "UNKNOWN"))
        requested = number(candidate.get("capital_required") or candidate.get("maximum_loss"))
        expected_value = number(candidate.get("expected_value"))
        probability = number(candidate.get("probability"), 0.5)
        symbol_exposure = number(payload["exposures"]["symbol"].get(symbol, 0))
        sector_exposure = number(payload["exposures"]["sector"].get(sector, 0))
        strategy_exposure = number(payload["exposures"]["strategy"].get(strategy, 0))
        symbol_pct = (symbol_exposure + requested) / net_liquidation * 100 if net_liquidation else 100
        sector_pct = (sector_exposure + requested) / net_liquidation * 100 if net_liquidation else 100
        strategy_pct = (strategy_exposure + requested) / net_liquidation * 100 if net_liquidation else 100
        marginal_heat = requested / net_liquidation * 100 if net_liquidation else 100
        penalty = (
            max(0, symbol_pct - 10) * 3
            + max(0, sector_pct - 25) * 1.5
            + max(0, strategy_pct - 35)
            + max(0, payload["capital"]["portfolio_heat_pct"] + marginal_heat - 20) * 3
        )
        efficiency = expected_value / requested * 100 if requested else 0
        score = clamp(65 + probability * 20 + min(15, efficiency) - penalty + (10 if symbol_exposure == 0 else 0))
        risk_budget = max(0, net_liquidation * 0.02)
        buying_power_budget = max(0, number(snapshot["buying_power"]) * 0.05)
        recommended_capital = min(requested or risk_budget, risk_budget, buying_power_budget)
        unit_risk = max(1.0, number(candidate.get("unit_risk") or requested, 1.0))
        quantity = int(recommended_capital // unit_risk) if recommended_capital else 0
        decision = "ACCEPT" if score >= 70 and quantity > 0 else "REVIEW" if score >= 50 else "REJECT"
        result = {
            "portfolio_fit_score": score,
            "decision": decision,
            "recommended_quantity": quantity,
            "recommended_capital": recommended_capital,
            "marginal_risk": requested,
            "marginal_portfolio_heat_pct": marginal_heat,
            "expected_value": expected_value,
            "projected_symbol_pct": symbol_pct,
            "projected_sector_pct": sector_pct,
            "projected_strategy_pct": strategy_pct,
            "reasons": self._fit_reasons(symbol_pct, sector_pct, strategy_pct, score),
            "risk_snapshot_id": snapshot["snapshot_id"],
            "policy_version": self.POLICY_VERSION,
        }
        with self.session_factory() as session:
            candidate_id = str(candidate.get("candidate_id") or candidate.get("opportunity_id") or uuid4().hex)
            row = session.scalar(select(PortfolioFitAssessmentModel).where(
                PortfolioFitAssessmentModel.portfolio_id == portfolio_id,
                PortfolioFitAssessmentModel.candidate_id == candidate_id,
                PortfolioFitAssessmentModel.risk_snapshot_id == snapshot["snapshot_id"],
            ))
            if row is None:
                row = PortfolioFitAssessmentModel(
                    assessment_id="M64-FIT-" + uuid4().hex.upper(),
                    portfolio_id=portfolio_id, candidate_id=candidate_id,
                    risk_snapshot_id=snapshot["snapshot_id"], symbol=symbol,
                    portfolio_fit_score=score, recommended_quantity=quantity,
                    recommended_capital=recommended_capital, decision=decision,
                    assessed_at=now(), payload_json={**candidate, **result},
                )
                session.add(row)
            else:
                row.symbol=symbol; row.portfolio_fit_score=score
                row.recommended_quantity=quantity; row.recommended_capital=recommended_capital
                row.decision=decision; row.assessed_at=now(); row.payload_json={**candidate, **result}
            session.commit()
        return result

    def stress(self, portfolio_id="PAPER-PRIMARY"):
        snapshot = self.current(portfolio_id) or self.build(portfolio_id)
        scenarios = snapshot["payload_json"]["risk"]["stress"]
        worst = min(scenarios.items(), key=lambda item: item[1]["estimated_pnl"])
        with self.session_factory() as session:
            row = PortfolioStressSnapshotModel(
                stress_snapshot_id="M64-STRESS-" + uuid4().hex.upper(),
                portfolio_id=portfolio_id,
                risk_snapshot_id=snapshot["snapshot_id"],
                generated_at=now(),
                worst_scenario=worst[0],
                worst_loss=abs(min(0, worst[1]["estimated_pnl"])),
                payload_json=scenarios,
            )
            session.add(row)
            session.commit()
        return {
            "risk_snapshot_id": snapshot["snapshot_id"],
            "worst_scenario": worst[0],
            "worst_loss": abs(min(0, worst[1]["estimated_pnl"])),
            "scenarios": scenarios,
        }

    def _fit_reasons(self, symbol_pct, sector_pct, strategy_pct, score):
        reasons = []
        if symbol_pct > 10:
            reasons.append("SYMBOL_CONCENTRATION_LIMIT")
        if sector_pct > 25:
            reasons.append("SECTOR_CONCENTRATION_LIMIT")
        if strategy_pct > 35:
            reasons.append("STRATEGY_CONCENTRATION_LIMIT")
        if not reasons:
            reasons.append("PORTFOLIO_DIVERSIFICATION_ACCEPTABLE")
        if score >= 80:
            reasons.append("STRONG_PORTFOLIO_FIT")
        return reasons

    def serialize(self, row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
