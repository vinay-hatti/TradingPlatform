from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
MAX_NEW_POSITIONS_ENV = "M64_MAX_NEW_POSITIONS"
MAX_NEW_POSITIONS_MIN = 1
MAX_NEW_POSITIONS_MAX = 100


@dataclass(frozen=True)
class PortfolioOptimizerRuntimeConfig:
    max_new_positions: int
    source: str

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


def load_portfolio_optimizer_config(
    env_file: Path | str | None = None,
) -> PortfolioOptimizerRuntimeConfig:
    """Load the authoritative M64 position cap from the project ``.env``.

    There is deliberately no code default and no process-environment fallback.
    A missing, malformed, or out-of-range value is a governance error: M64 must
    fail closed instead of silently changing the portfolio construction policy.
    """

    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if not path.exists():
        raise ValueError(
            f"M64 optimizer configuration file is missing: {path}; "
            f"configure {MAX_NEW_POSITIONS_ENV} in the project .env"
        )
    values = dict(dotenv_values(path))
    raw = values.get(MAX_NEW_POSITIONS_ENV)
    if raw is None or str(raw).strip() == "":
        raise ValueError(
            f"{MAX_NEW_POSITIONS_ENV} must be configured in {path}"
        )
    normalized = str(raw).strip()
    if not normalized.isdigit():
        raise ValueError(
            f"{MAX_NEW_POSITIONS_ENV} must be an integer between "
            f"{MAX_NEW_POSITIONS_MIN} and {MAX_NEW_POSITIONS_MAX}"
        )
    value = int(normalized)
    if not MAX_NEW_POSITIONS_MIN <= value <= MAX_NEW_POSITIONS_MAX:
        raise ValueError(
            f"{MAX_NEW_POSITIONS_ENV} must be between "
            f"{MAX_NEW_POSITIONS_MIN} and {MAX_NEW_POSITIONS_MAX}; "
            f"found {value}"
        )
    return PortfolioOptimizerRuntimeConfig(
        max_new_positions=value,
        source=f"{path}:{MAX_NEW_POSITIONS_ENV}",
    )
