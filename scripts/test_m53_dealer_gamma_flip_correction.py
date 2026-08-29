from __future__ import annotations

from datetime import date
from pathlib import Path

from trading_ai.institutional_market_structure.contracts import DealerPositioningPolicy
from trading_ai.institutional_market_structure.engine import (
    InstitutionalMarketStructureEngine,
    _M,
    _sign,
)


def metric(strike: float, right: str, oi: float, sign: float) -> _M:
    return _M(
        expiry=date(2026, 8, 28), dte=30, strike=strike, right=right,
        oi=oi, volume=0.0, iv=0.30, bid=0.0, ask=0.0, mid=0.0,
        delta=0.0, gamma=0.0, vanna=0.0, charm=0.0, sign=sign,
        gex=0.0, dex=0.0, vex=0.0, cex=0.0, premium=0.0,
        spread=None, trade_ok=False,
    )


def main() -> None:
    assert _sign("CALL", "street_proxy") == -1.0
    assert _sign("PUT", "street_proxy") == 1.0
    assert _sign("CALL", "customer_long_proxy") == 1.0
    assert _sign("PUT", "customer_long_proxy") == -1.0
    assert _sign("CALL", "unsigned_market_exposure") == 1.0
    assert _sign("PUT", "unsigned_market_exposure") == 1.0

    engine = InstitutionalMarketStructureEngine(DealerPositioningPolicy())
    flip, lower, upper, confidence = engine._gamma_flip_grid(
        [metric(80.0, "CALL", 100.0, -1.0), metric(90.0, "PUT", 100.0, 1.0)],
        100.0,
    )
    assert flip is not None
    assert lower is not None and upper is not None and lower <= flip <= upper
    assert 0.0 < confidence <= 1.0

    pages = Path("ui/workstation/src/pages.tsx").read_text(encoding="utf-8")
    expected = "r.gamma_flip==null?'No flip detected':money(r.gamma_flip)"
    assert expected in pages
    assert "ESTIMATOR_VERSION='44.2.1'" in Path(
        "src/trading_ai/institutional_market_structure/engine.py"
    ).read_text(encoding="utf-8")
    print("Milestone 53 dealer gamma-flip correction assertions passed.")


if __name__ == "__main__":
    main()
