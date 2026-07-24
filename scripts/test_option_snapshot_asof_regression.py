from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine, insert
from sqlalchemy.orm import Session, sessionmaker

from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.options.repository_snapshot_provider import RepositoryOptionSnapshotProvider


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    table = Table(
        "option_contract_history",
        metadata,
        Column("underlying_symbol", String, nullable=False),
        Column("quote_date", Date, nullable=False),
        Column("expiry", Date, nullable=False),
        Column("strike", Float, nullable=False),
        Column("option_type", String, nullable=False),
        Column("bid", Float, nullable=False),
        Column("ask", Float, nullable=False),
        Column("last", Float, nullable=False),
        Column("volume", Integer, nullable=False),
        Column("open_interest", Integer, nullable=False),
        Column("implied_volatility", Float, nullable=False),
        Column("option_symbol", String, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(table), [
            {
                "underlying_symbol": "NVDA",
                "quote_date": date(2026, 7, 23),
                "expiry": date(2026, 9, 18),
                "strike": 180.0,
                "option_type": "call",
                "bid": 8.0,
                "ask": 8.4,
                "last": 8.2,
                "volume": 500,
                "open_interest": 5000,
                "implied_volatility": 0.35,
                "option_symbol": "O:NVDA260918C00180000",
            },
            {
                "underlying_symbol": "NVDA",
                "quote_date": date(2026, 7, 22),
                "expiry": date(2026, 9, 18),
                "strike": 180.0,
                "option_type": "call",
                "bid": 7.0,
                "ask": 7.4,
                "last": 7.2,
                "volume": 400,
                "open_interest": 4900,
                "implied_volatility": 0.34,
                "option_symbol": "O:NVDA260918C00180000",
            },
        ])
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_repository_uses_latest_snapshot_on_or_before_scan_date():
    factory = _session_factory()
    with factory() as session:
        rows = OptionChainRepository(session).get_latest_snapshot(
            "NVDA", as_of=date(2026, 7, 24)
        )
    assert rows
    assert {str(row["quote_date"]) for row in rows} == {"2026-07-23"}
    assert rows[0]["contract_ticker"] == "O:NVDA260918C00180000"


def test_provider_accepts_prior_trading_day_snapshot():
    factory = _session_factory()
    provider = RepositoryOptionSnapshotProvider(session_factory=factory)
    contracts = provider.chain(
        "NVDA",
        signal="CALL",
        target_expiration=date(2026, 9, 18),
        target_strike=180.0,
        as_of=date(2026, 7, 24),
        expiration_window_days=10,
        strike_window_pct=0.15,
    )
    assert len(contracts) == 1
    contract = contracts[0]
    assert contract.contract_ticker == "O:NVDA260918C00180000"
    assert contract.expiration_date == "2026-09-18"
    assert contract.quote_timestamp == "2026-07-23"
    assert contract.dte == 56


def main():
    test_repository_uses_latest_snapshot_on_or_before_scan_date()
    test_provider_accepts_prior_trading_day_snapshot()
    print("Option snapshot as-of regression tests passed.")


if __name__ == "__main__":
    main()
