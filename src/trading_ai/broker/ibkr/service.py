from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select

from trading_ai.portfolio_management.database_models import PortfolioAccountModel
from .database_models import BrokerAccountBindingModel, BrokerAccountSnapshotModel, BrokerPositionSnapshotModel
from .models import IbkrPaperConnectionConfig
from .transport import IbkrTransport


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24].upper()


class IbkrPaperAccountService:
    def __init__(self, session_factory: Callable, transport: IbkrTransport | None = None) -> None:
        self.session_factory = session_factory
        self.transport = transport

    def register(
        self,
        *,
        portfolio_id: str,
        broker_account_id: str,
        base_currency: str = "USD",
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 50,
        read_only: bool = True,
    ) -> dict:
        config = IbkrPaperConnectionConfig(
            host=host, port=port, client_id=client_id, environment="PAPER",
            expected_account_id=broker_account_id, read_only=read_only,
        )
        config.validate()
        broker_account_id = broker_account_id.upper().strip()
        now = _now()
        binding_id = _id("IBKR-", f"{portfolio_id}|{broker_account_id}")
        session = self.session_factory()
        try:
            account = session.get(PortfolioAccountModel, portfolio_id)
            if account is None:
                account = PortfolioAccountModel(
                    portfolio_id=portfolio_id,
                    name="IBKR Paper Trading",
                    base_currency=base_currency.upper(),
                    initial_capital=0.0,
                    status="PENDING_BROKER_SYNC",
                    created_at=now,
                    metadata_json={"paper_only": True, "broker": "INTERACTIVE_BROKERS"},
                )
                session.add(account)
            binding = session.get(BrokerAccountBindingModel, binding_id)
            payload = dict(
                portfolio_id=portfolio_id, broker_name="INTERACTIVE_BROKERS",
                broker_environment="PAPER", broker_account_id=broker_account_id,
                base_currency=base_currency.upper(), host=host, port=port,
                client_id=client_id, read_only=read_only, live_trading_enabled=False,
                status="REGISTERED_NOT_VERIFIED", updated_at=now,
                metadata_json={"paper_only": True, "credentials_stored": False},
            )
            if binding is None:
                binding = BrokerAccountBindingModel(binding_id=binding_id, created_at=now, **payload)
                session.add(binding)
            else:
                for key, value in payload.items():
                    setattr(binding, key, value)
            session.commit()
            return self._binding_dict(binding)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def verify_and_sync(self, portfolio_id: str) -> dict:
        if self.transport is None:
            raise RuntimeError("IBKR transport is required for account synchronization")
        session = self.session_factory()
        try:
            binding = session.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id == portfolio_id))
            if binding is None:
                raise LookupError(f"No IBKR paper binding registered for {portfolio_id}")
            # Account/position synchronization is always a read-only broker session.
            # The persisted binding may remain paper-order-capable (read_only=False)
            # for the separate order-routing transport; never pass that capability
            # into the connectivity-verification transport.
            config = IbkrPaperConnectionConfig(
                host=binding.host, port=binding.port, client_id=binding.client_id,
                environment=binding.broker_environment, expected_account_id=binding.broker_account_id,
                read_only=True,
            )
            status = self.transport.connect(config)
            if not status.connected:
                raise RuntimeError(status.message or "IBKR connection failed")
            accounts = {value.upper() for value in status.account_ids}
            if binding.broker_account_id.upper() not in accounts:
                raise RuntimeError("Connected IBKR session does not contain the registered paper account")
            if any(not account.startswith("DU") for account in accounts):
                raise RuntimeError("Paper-only safeguard rejected a non-DU account in the connected session")
            summary = self.transport.account_summary(binding.broker_account_id)
            positions = self.transport.positions(binding.broker_account_id)
            captured_at = summary.captured_at
            snapshot_id = _id("IBKR-SNAP-", f"{portfolio_id}|{captured_at}")
            session.add(BrokerAccountSnapshotModel(
                snapshot_id=snapshot_id, binding_id=binding.binding_id,
                portfolio_id=portfolio_id, broker_account_id=binding.broker_account_id,
                captured_at=captured_at, base_currency=summary.base_currency,
                net_liquidation=summary.net_liquidation, total_cash_value=summary.total_cash_value,
                available_funds=summary.available_funds, buying_power=summary.buying_power,
                excess_liquidity=summary.excess_liquidity, raw_json=summary.raw,
            ))
            for item in positions:
                pid = _id("IBKR-POS-", f"{snapshot_id}|{item.contract_id}|{item.local_symbol}")
                session.add(BrokerPositionSnapshotModel(
                    snapshot_position_id=pid, account_snapshot_id=snapshot_id,
                    portfolio_id=portfolio_id, broker_account_id=item.broker_account_id,
                    contract_id=item.contract_id, symbol=item.symbol,
                    local_symbol=item.local_symbol, security_type=item.security_type,
                    currency=item.currency, exchange=item.exchange,
                    quantity=item.quantity, average_cost=item.average_cost,
                    expiry=item.expiry, strike=item.strike, right=item.right,
                    multiplier=item.multiplier, captured_at=item.captured_at,
                    raw_json=item.raw,
                ))
            # Preserve active paper-order routing while refreshing read-side account state.
            sync_status = "VERIFIED_PAPER_TRADING" if (binding.status == "VERIFIED_PAPER_TRADING" and not binding.read_only) else "VERIFIED_READ_ONLY"
            binding.status = sync_status
            binding.updated_at = _now()
            account = session.get(PortfolioAccountModel, portfolio_id)
            if account is not None:
                account.base_currency = summary.base_currency
                account.initial_capital = account.initial_capital or summary.net_liquidation
                account.status = "ACTIVE"
                account.metadata_json = {
                    **(account.metadata_json or {}),
                    "broker_account_id": binding.broker_account_id,
                    "broker_verified": True,
                    "broker_read_only": True,
                    "last_broker_sync": captured_at,
                    "net_liquidation": summary.net_liquidation,
                    "total_cash_value": summary.total_cash_value,
                    "available_funds": summary.available_funds,
                    "buying_power": summary.buying_power,
                }
            session.commit()
            return {
                "status": sync_status,
                "portfolio_id": portfolio_id,
                "broker_account_id_masked": self.mask_account(binding.broker_account_id),
                "account_summary": asdict(summary),
                "positions_imported": len(positions),
                "snapshot_id": snapshot_id,
                "live_trading_enabled": False,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            try:
                self.transport.disconnect()
            except Exception:
                pass
            session.close()

    @staticmethod
    def mask_account(account_id: str) -> str:
        return account_id[:2] + "*" * max(0, len(account_id) - 4) + account_id[-2:]

    @classmethod
    def _binding_dict(cls, binding: BrokerAccountBindingModel) -> dict:
        return {
            "binding_id": binding.binding_id,
            "portfolio_id": binding.portfolio_id,
            "broker": binding.broker_name,
            "environment": binding.broker_environment,
            "broker_account_id_masked": cls.mask_account(binding.broker_account_id),
            "base_currency": binding.base_currency,
            "host": binding.host,
            "port": binding.port,
            "client_id": binding.client_id,
            "read_only": binding.read_only,
            "live_trading_enabled": binding.live_trading_enabled,
            "status": binding.status,
        }
