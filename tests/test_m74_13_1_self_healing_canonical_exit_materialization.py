from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService


def _service_with_temp_canonical_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'canonical.db'}")
    CanonicalOrderModel.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    import sys, types
    database_session = types.ModuleType("trading_ai.database.session")
    database_session.SessionLocal = factory
    monkeypatch.setitem(sys.modules, "trading_ai.database.session", database_session)
    return DynamicPositionManagementService.__new__(DynamicPositionManagementService), factory


def test_missing_canonical_exit_is_materialized_durably_and_idempotently(monkeypatch, tmp_path):
    svc, factory = _service_with_temp_canonical_db(monkeypatch, tmp_path)
    position = SimpleNamespace(
        position_id="POS-TEST",
        portfolio_id="PAPER-PRIMARY",
        trade_plan_id="TP-TEST",
        execution_id="XI-TEST",
        strategy="BULL_CALL_SPREAD",
    )
    instruction = SimpleNamespace(
        instruction_id="PXI-TEST",
        action="SCALE_OUT",
        payload={"label":"TARGET_1","execution_scope":"FULL_STRATEGY","exit_method":"ATOMIC_BAG"},
    )
    request = SimpleNamespace(
        aggregate_id="M62-EXIT-PXI-TEST",
        client_order_id="M62-EXIT-CLIENT-PXI-TEST",
        order_type="LMT",
        time_in_force="DAY",
        quantity=1.0,
        limit_price=-4.25,
        stop_price=None,
        outside_regular_hours=False,
    )
    legs=[
        {"contract_id":101,"ratio":1,"side":"SELL","symbol":"SPY","expiry":"2026-09-25","strike":771.0,"option_right":"CALL"},
        {"contract_id":102,"ratio":1,"side":"BUY","symbol":"SPY","expiry":"2026-09-25","strike":794.0,"option_right":"CALL"},
    ]

    first = svc._ensure_canonical_exit_order(position, instruction, request, legs)
    assert first["created"] is True
    assert first["durable_before_transmit"] is True
    assert first["source"] == "M74_13_1_SELF_HEALING_MATERIALIZATION"

    with factory() as s:
        row=s.get(CanonicalOrderModel, request.aggregate_id)
        assert row is not None
        assert row.state == "VALIDATED"
        assert row.strategy_name == "BULL_CALL_SPREAD"
        assert row.total_quantity == 1.0
        assert row.limit_price == -4.25
        assert row.metadata_json["managed_position_id"] == "POS-TEST"
        assert row.metadata_json["exit_instruction_id"] == "PXI-TEST"
        assert row.metadata_json["durable_before_transmit"] is True
        assert row.legs_json == legs

    second = svc._ensure_canonical_exit_order(position, instruction, request, legs)
    assert second["created"] is False
    assert second["source"] == "EXISTING_CANONICAL_EXIT_ORDER"
    with factory() as s:
        assert len(list(s.scalars(select(CanonicalOrderModel)))) == 1


def test_exit_routing_materializes_canonical_before_broker_submit():
    import inspect
    source=inspect.getsource(DynamicPositionManagementService._submit_exit)
    assert source.index("_ensure_canonical_exit_order") < source.index("service.submit(request)")
    assert source.rindex("_ensure_canonical_exit_order") < source.index("self._submit_strategy_combo(service,request)")
    helper=inspect.getsource(DynamicPositionManagementService._submit_strategy_combo)
    assert "return service.submit_combo(request)" in helper
    assert "canonical_exit_order" in source


def test_submission_failed_instructions_are_retryable_and_success_clears_stale_error():
    import inspect
    source=inspect.getsource(DynamicPositionManagementService.evaluate_position)
    assert '{"ARMED","SUBMISSION_FAILED"}' in source
    assert 'payload.pop("submission_error", None)' in source
    assert 'payload.pop("submission_failed_at", None)' in source
    assert 'submission_attempt_count' in source


def test_combo_exit_preserves_complete_m74_10_strategy_level_metadata_contract():
    import inspect
    source=inspect.getsource(DynamicPositionManagementService._submit_exit)
    assert "'strategy_level_exit':True" in source
    assert "'includes_short_legs':True" in source
    assert "'closing_combo':True" in source
    assert "'strategy_type':position.strategy" in source
    assert "close_action='SELL' if original=='BUY' else 'BUY'" in source
    helper=inspect.getsource(DynamicPositionManagementService._submit_strategy_combo)
    assert "return service.submit_combo(request)" in helper
