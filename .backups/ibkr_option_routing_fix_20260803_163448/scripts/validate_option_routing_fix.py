#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1] if (SCRIPT.parents[1] / "src").exists() else SCRIPT.parents[2]
module_path = ROOT / "src/trading_ai/broker/ibkr/order_models.py"
spec = importlib.util.spec_from_file_location("ibkr_order_models_validation", module_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Request = module.IbkrPaperOrderRequest

base = dict(aggregate_id="A", client_order_id="C", portfolio_id="PAPER-PRIMARY", broker_account_id="DU123", symbol="VOO", security_type="OPT", side="BUY", quantity=1, order_type="LMT", limit_price=5.0, contract_id=123, local_symbol="VOO 260918C00100000", expiry="20260918", strike=100.0, right="C", multiplier="100")
Request(**base).validate()
for key, value in (("contract_id",0),("local_symbol",""),("expiry",""),("strike",0),("right","CALL"),("multiplier","")):
    values={**base,key:value}
    try: Request(**values).validate()
    except ValueError: pass
    else: raise AssertionError(f"invalid option request accepted: {key}={value!r}")
Request(aggregate_id="S",client_order_id="SC",portfolio_id="PAPER-PRIMARY",broker_account_id="DU123",symbol="AAPL",security_type="STK",side="BUY",quantity=1).validate()
print("Option routing contract qualification validation passed.")
