from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
CAPITAL_ENV = "TRADING_AI_TRADE_BUILDER_CAPITAL"
RISK_ENV = "TRADING_AI_TRADE_BUILDER_RISK_BUDGET_PCT"


@dataclass(frozen=True)
class TradeBuilderRiskConfig:
    capital: float
    risk_budget_pct: float
    risk_budget_amount: float
    source: str

    def as_dict(self) -> dict[str, float | str]:
        return asdict(self)


def _read_value(values: dict[str, object], name: str, default: str) -> str:
    # The project .env intentionally has precedence so editing it changes the
    # next API request without requiring the API process environment to change.
    value = values.get(name)
    if value is None or str(value).strip() == "":
        value = os.getenv(name, default)
    return str(value).strip()


def load_trade_builder_risk_config(env_file: Path | str | None = None) -> TradeBuilderRiskConfig:
    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    values = dict(dotenv_values(path)) if path.exists() else {}
    try:
        capital = float(_read_value(values, CAPITAL_ENV, "100000"))
        risk_budget_pct = float(_read_value(values, RISK_ENV, "1"))
    except ValueError as exc:
        raise ValueError("Trade Builder capital/risk configuration must be numeric") from exc
    if capital <= 0:
        raise ValueError("Trade Builder capital must be greater than zero")
    if risk_budget_pct <= 0:
        raise ValueError("Trade Builder risk budget percentage must be greater than zero")
    return TradeBuilderRiskConfig(
        capital=capital,
        risk_budget_pct=risk_budget_pct,
        risk_budget_amount=capital * risk_budget_pct / 100.0,
        source=str(path) if path.exists() else "process-environment/defaults",
    )
