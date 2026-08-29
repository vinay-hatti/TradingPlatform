from __future__ import annotations
import logging
import threading
import os
import time
import fcntl
from pathlib import Path
from decimal import Decimal
from typing import Any
from .models import IbkrPaperConnectionConfig
from .price_normalization import is_price_on_increment, normalize_limit_price, normalize_signed_combo_price
LOGGER = logging.getLogger(__name__)


def _normalize_order_compatibility(order):
    """Disable legacy IBKR order flags rejected by modern TWS/Gateway.

    ibapi 9.81.1-1 initializes eTradeOnly and firmQuoteOnly to True even
    though current TWS/Gateway versions reject both fields.  Normalize them
    explicitly for every outbound order while leaving nbboPriceCap at the
    IBKR unset sentinel.
    """
    if hasattr(order, "eTradeOnly"):
        order.eTradeOnly = False
    if hasattr(order, "firmQuoteOnly"):
        order.firmQuoteOnly = False
    return order

from .order_models import (
    IbkrPaperComboLegRequest,
    IbkrPaperComboOrderRequest,
    IbkrPaperExecution,
    IbkrPaperOrderRequest,
    IbkrPaperOrderStatus,
    utc_now_iso,
)

class IbapiPaperOrderTransport:
    def __init__(self): self._app=None; self._config=None; self._thread=None; self._lock_handle=None; self._contract_rule_cache={}; self._combo_rule_cache={}; self._last_outbound_price_validation={}
    def _acquire_client_lock(self, client_id:int, timeout_seconds:float):
        path=Path(os.getenv("TRADING_AI_IBKR_TRANSPORT_LOCK_DIR","/tmp"))/f"trading_ai_ibkr_client_{int(client_id)}.lock"
        handle=open(path,"a+")
        deadline=time.monotonic()+max(1.0,float(timeout_seconds))
        while True:
            try:
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);self._lock_handle=handle;return
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    handle.close();raise TimeoutError(f"IBKR client {client_id} transport lock timed out: {path}")
                time.sleep(0.1)
    def _release_client_lock(self):
        handle=self._lock_handle;self._lock_handle=None
        if handle is not None:
            try:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
            finally:handle.close()
    def connect(self, config: IbkrPaperConnectionConfig):
        config.validate();self._acquire_client_lock(config.client_id,config.timeout_seconds)
        app=self._build_app()
        try:app.connect(config.host,config.port,clientId=config.client_id)
        except Exception:
            self._release_client_lock();raise
        thread=threading.Thread(target=app.run,daemon=True); thread.start()
        if not app.api_ready.wait(config.timeout_seconds): app.disconnect(); self._release_client_lock(); raise TimeoutError("IBKR API readiness timed out")
        if not app.accounts_ready.is_set(): app.reqManagedAccts()
        if not app.accounts_ready.wait(config.timeout_seconds): app.disconnect(); self._release_client_lock(); raise TimeoutError("IBKR account discovery timed out")
        accounts=tuple(sorted(app.managed_accounts))
        if config.expected_account_id.upper() not in accounts: app.disconnect(); self._release_client_lock(); raise RuntimeError("registered paper account not exposed")
        if any(not a.startswith("DU") for a in accounts): app.disconnect(); self._release_client_lock(); raise RuntimeError("non-paper managed account rejected")
        self._app=app; self._config=config; self._thread=thread
        return {"status":"CONNECTED_PAPER_ORDER_CAPABLE","managed_accounts":accounts,"server_version":app.serverVersion(),"live_trading_enabled":False}
    def disconnect(self):
        if self._app is not None: self._app.disconnect()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=2)
        self._app=None; self._config=None; self._thread=None; self._release_client_lock()
    def health(self):
        if self._app is None or not self._app.isConnected(): raise RuntimeError("IBKR transport is not connected")
        return {"connected":True,"managed_accounts":tuple(sorted(self._app.managed_accounts)),"server_version":self._app.serverVersion()}
    def set_order_id_floor(self, minimum_order_id: int) -> int:
        """Advance the connected IBKR order-id cursor without ever moving it backward."""
        app = self._require()
        minimum = max(1, int(minimum_order_id))
        if app.next_id is None:
            raise RuntimeError("IBKR order id unavailable")
        if app.next_id < minimum:
            app.next_id = minimum
        return int(app.next_id)

    def reserve_order_id(self) -> int:
        """Reserve the next broker order id before any order is transmitted.

        M74.6 uses this to durably persist SUBMISSION_PENDING broker lineage before
        placeOrder() can make an order visible in TWS.
        """
        return int(self._require().reserve_order_id())

    def _request_contract_rule_details(self, contract, exchange: str, cache: dict, cache_key) -> dict:
        if cache_key in cache:
            return dict(cache[cache_key])
        app=self._require();request_id=app.next_request_id();app.begin_contract_details(request_id);app.reqContractDetails(request_id,contract)
        if not app.contract_details_ready[request_id].wait(self._config.timeout_seconds):
            raise TimeoutError(f"IBKR contract market-rule lookup timed out for {cache_key}")
        rows=app.contract_detail_rows.pop(request_id,[]);app.contract_details_ready.pop(request_id,None);error_text=app.contract_detail_errors.pop(request_id,"")
        if not rows:
            detail=f": {error_text}" if error_text else ""
            raise LookupError(f"IBKR contract details unavailable for {cache_key}{detail}")
        target=str(exchange or "SMART").upper();selected=rows[0]
        for row in rows:
            valid=[x.strip().upper() for x in str(row.get("valid_exchanges") or "").split(",") if x.strip()]
            if target in valid or str(row.get("exchange") or "").upper()==target:
                selected=row;break
        cache[cache_key]=dict(selected);return dict(selected)

    def _contract_rule_details(self, contract_id: int, exchange: str = "SMART") -> dict:
        Contract,_=self._types();contract=Contract();contract.conId=int(contract_id);contract.exchange=str(exchange or "SMART")
        key=(int(contract_id),str(exchange or "SMART").upper())
        return self._request_contract_rule_details(contract,exchange,self._contract_rule_cache,key)

    def _market_rule_increments(self, market_rule_id: int) -> list[dict]:
        app=self._require(); rule_id=int(market_rule_id)
        app.begin_market_rule(rule_id); app.reqMarketRule(rule_id)
        if not app.market_rule_ready[rule_id].wait(self._config.timeout_seconds):
            raise TimeoutError(f"IBKR market rule {rule_id} timed out")
        rows=list(app.market_rule_rows.pop(rule_id,[]) or []); app.market_rule_ready.pop(rule_id,None)
        return rows

    @staticmethod
    def _market_rule_id(details: dict, exchange: str) -> tuple[int | None, list[str]]:
        valid=[x.strip().upper() for x in str(details.get("valid_exchanges") or "").split(",") if x.strip()]
        ids=[x.strip() for x in str(details.get("market_rule_ids") or "").split(",") if x.strip()]
        target=str(exchange or "SMART").upper();market_rule_id=None
        if target in valid:
            index=valid.index(target)
            if index < len(ids) and ids[index].isdigit():market_rule_id=int(ids[index])
        if market_rule_id is None:
            for raw in ids:
                if raw.isdigit():market_rule_id=int(raw);break
        return market_rule_id,valid

    def _normalization_inputs(self, details: dict, exchange: str, identity: str) -> tuple[list[dict], float, int | None, str, list[str]]:
        market_rule_id,valid=self._market_rule_id(details,exchange);increments=[];source="CONTRACT_MIN_TICK"
        if market_rule_id is not None:
            try:
                increments=self._market_rule_increments(market_rule_id);source="IBKR_MARKET_RULE" if increments else source
            except Exception as exc:
                LOGGER.warning("IBKR market-rule lookup failed %s rule=%s: %s; falling back to minTick",identity,market_rule_id,exc)
        min_tick=float(details.get("min_tick") or 0.0)
        if not increments and min_tick <= 0:
            raise ValueError(f"IBKR exposed no usable order price increment for {identity}; refusing to transmit")
        return increments,min_tick,market_rule_id,source,valid

    def normalize_contract_limit_price(self, *, contract_id: int, price: float, side: str, exchange: str = "SMART") -> dict:
        details=self._contract_rule_details(int(contract_id),exchange)
        increments,min_tick,market_rule_id,source,valid=self._normalization_inputs(details,exchange,f"conId={int(contract_id)}")
        result=normalize_limit_price(float(price),str(side),increments,min_tick)
        result.update({"contract_id":int(contract_id),"exchange":str(exchange or "SMART").upper(),"market_rule_id":market_rule_id,"source":source,"valid_exchanges":valid,"validation":"BROKER_RULE_VALID"})
        return result

    def normalize_option_limit_price(self, *, contract_id: int, price: float, side: str, exchange: str = "SMART") -> dict:
        return self.normalize_contract_limit_price(contract_id=contract_id,price=price,side=side,exchange=exchange)

    @staticmethod
    def _combo_cache_key(request: IbkrPaperComboOrderRequest):
        legs=tuple((int(x.contract_id),int(x.ratio),str(x.action).upper(),str(x.exchange or "SMART").upper()) for x in request.combo_legs)
        return (str(request.symbol).upper(),str(request.currency).upper(),str(request.exchange or "SMART").upper(),legs)

    @staticmethod
    def _build_combo_contract(request: IbkrPaperComboOrderRequest):
        from ibapi.contract import ComboLeg, Contract
        contract=Contract();contract.symbol=request.symbol;contract.secType="BAG";contract.currency=request.currency;contract.exchange=request.exchange;contract.comboLegs=[]
        for item in request.combo_legs:
            leg=ComboLeg();leg.conId=int(item.contract_id);leg.ratio=int(item.ratio);leg.action=item.action.upper();leg.exchange=item.exchange;contract.comboLegs.append(leg)
        return contract

    @staticmethod
    def _combo_increment_candidates() -> list[float]:
        """Candidate grids used only to discover a TWS-valid BAG price.

        IBKR does not support reqContractDetails() for BAG contracts and the
        market-data minTick is explicitly not authoritative for combo order
        placement.  Correctness therefore comes from the staged TWS validation
        below, not from this ladder.  The ladder only controls how quickly we
        converge on a valid price while preserving the governed debit/credit
        economic limit.
        """
        raw=os.getenv("TRADING_AI_IBKR_COMBO_PRICE_INCREMENT_CANDIDATES","0.01,0.05,0.10,0.25,0.50,1.00")
        values=[]
        for item in str(raw).split(","):
            try: value=float(item.strip())
            except (TypeError,ValueError): continue
            if value > 0 and value not in values: values.append(value)
        if not values:
            raise ValueError("No BAG price-validation candidate increments configured")
        return sorted(values)

    def _combo_candidate_normalizations(self, request: IbkrPaperComboOrderRequest) -> list[dict]:
        request.validate();rows=[];seen=set()
        for increment in self._combo_increment_candidates():
            result=normalize_signed_combo_price(float(request.limit_price),[],float(increment))
            price=float(result["normalized_price"])
            key=round(price,12)
            if key in seen: continue
            seen.add(key)
            result.update({
                "security_type":"BAG",
                "symbol":request.symbol,
                "exchange":str(request.exchange or "SMART").upper(),
                "market_rule_id":None,
                "source":"BAG_PRICE_GRID_DISCOVERY",
                "validation":"PRICE_GRID_CANDIDATE",
                "combo_legs":[{"contract_id":int(x.contract_id),"ratio":int(x.ratio),"action":str(x.action).upper(),"exchange":x.exchange} for x in request.combo_legs],
            })
            rows.append(result)
        return rows

    @staticmethod
    def _build_combo_order(request: IbkrPaperComboOrderRequest, *, limit_price: float, transmit: bool, order_ref: str | None = None):
        from ibapi.order import Order
        order=_normalize_order_compatibility(Order())
        order.account=request.broker_account_id;order.action=request.side;order.totalQuantity=Decimal(str(request.quantity));order.orderType=request.order_type.upper();order.tif=request.time_in_force.upper();order.outsideRth=request.outside_regular_hours;order.transmit=bool(transmit);order.orderRef=order_ref or request.aggregate_id;order.lmtPrice=float(limit_price)
        return order

    def _stage_combo_price(self, request: IbkrPaperComboOrderRequest, contract, normalization: dict) -> tuple[int,dict]:
        """Ask TWS to validate the exact BAG price without transmitting it.

        Transmit=False creates a local staged order in TWS.  Error 110 therefore
        rejects an invalid price before broker transmission.  A positive
        OPEN_ORDER/ORDER_STATUS acknowledgement means the exact candidate has
        passed TWS order-entry validation and can be promoted unchanged.
        """
        app=self._require();oid=app.reserve_order_id();app.begin_order_ack(oid)
        order=self._build_combo_order(request,limit_price=float(normalization["normalized_price"]),transmit=False,order_ref=f"{request.aggregate_id}:PRICE_VALIDATE")
        LOGGER.info("IBKR staging BAG price validation order_id=%s aggregate_id=%s price=%s",oid,request.aggregate_id,normalization["normalized_price"])
        app.placeOrder(oid,contract,order)
        ack=self.wait_for_order_acknowledgement(oid)
        return oid,ack

    def _cancel_local_staged_order(self, order_id: int) -> None:
        app=self._require()
        try:
            from ibapi.order_cancel import OrderCancel
            app.cancelOrder(int(order_id),OrderCancel())
        except (ImportError,TypeError):
            app.cancelOrder(int(order_id))

    def _verify_local_staged_order(self, order_id: int) -> dict:
        """Verify a transmit=False order through TWS open-order truth.

        A staged order can be created successfully in TWS without producing an
        immediate orderStatus callback.  A wait timeout is therefore not a
        rejection.  reqOpenOrders() is the authoritative second check for the
        same API session.  Only an explicit error callback is treated as a
        validation rejection.
        """
        app=self._require();oid=int(order_id)
        # An error can race the acknowledgement timeout.  Honor it before
        # requesting an open-order snapshot.
        latest=dict(app.order_ack_payloads.get(oid) or {})
        if str(latest.get("callback") or "").upper()=="ERROR":
            return latest
        app.begin_orders();app.reqOpenOrders()
        timeout=max(0.25,min(float(self._config.timeout_seconds),2.0))
        if app.orders_ready.wait(timeout):
            row=dict(app.order_rows.get(oid) or {})
            if row:
                return {
                    "acknowledged":True,
                    "callback":"OPEN_ORDER_VERIFY",
                    "status":str(row.get("status") or "STAGED").upper().replace(" ","_"),
                    "permanent_id":int(row.get("permanent_id") or 0),
                    "broker_order_id":oid,
                    "received_at":utc_now_iso(),
                    "verification":"REQ_OPEN_ORDERS",
                }
        latest=dict(app.order_ack_payloads.get(oid) or {})
        if str(latest.get("callback") or "").upper()=="ERROR":
            return latest
        return {
            "acknowledged":False,
            "callback":"INCONCLUSIVE",
            "status":"STAGE_VALIDATION_INCONCLUSIVE",
            "broker_order_id":oid,
            "received_at":utc_now_iso(),
            "verification":"REQ_OPEN_ORDERS",
        }

    def validate_combo_limit_price(self, request: IbkrPaperComboOrderRequest, *, keep_stage_for_transmit: bool) -> tuple[dict,int|None]:
        request.validate();contract=self._build_combo_contract(request);attempts=[]
        for normalization in self._combo_candidate_normalizations(request):
            stage_id,ack=self._stage_combo_price(request,contract,normalization)
            if not bool(ack.get("acknowledged")) and str(ack.get("callback") or "").upper() in {"TIMEOUT","UNKNOWN","UNAVAILABLE"}:
                ack=self._verify_local_staged_order(stage_id)
            attempts.append({"candidate":dict(normalization),"ack":dict(ack),"stage_order_id":int(stage_id)})
            if bool(ack.get("acknowledged")):
                normalized=dict(normalization);normalized.update({"valid":True,"validation":"TWS_STAGE_VALID","stage_order_id":int(stage_id),"staged_ack":dict(ack),"candidate_attempt_count":len(attempts),"candidate_attempts":attempts})
                if keep_stage_for_transmit:
                    return normalized,int(stage_id)
                self._cancel_local_staged_order(stage_id)
                return normalized,None
            callback=str(ack.get("callback") or "").upper()
            code=ack.get("error_code")
            if callback=="ERROR":
                numeric_code=int(code or 0)
                if numeric_code==110:
                    continue
                raise ValueError(f"IBKR TWS rejected BAG validation candidate before transmission: code={numeric_code} message={ack.get('error_message')}")
            # No explicit TWS/IBKR error means we have not proved either valid
            # or invalid.  Fail closed without calling it a broker rejection.
            self._cancel_local_staged_order(stage_id)
            raise TimeoutError(f"IBKR TWS BAG staged-price validation inconclusive before transmission: order_id={stage_id} callback={callback or 'NONE'} status={ack.get('status')}")
        raise ValueError(f"IBKR TWS rejected every configured BAG price candidate with error 110; refusing to transmit. attempts={len(attempts)}")

    def normalize_combo_limit_price(self, request: IbkrPaperComboOrderRequest) -> dict:
        """Compatibility wrapper returning a TWS-staged, broker-safe BAG price."""
        result,_=self.validate_combo_limit_price(request,keep_stage_for_transmit=False)
        return result

    def _record_outbound_price_validation(self, aggregate_id: str, payload: dict) -> None:
        self._last_outbound_price_validation[str(aggregate_id)] = dict(payload)

    def last_outbound_price_validation(self, aggregate_id: str) -> dict:
        return dict(self._last_outbound_price_validation.get(str(aggregate_id)) or {})

    @staticmethod
    def _assert_valid_normalization(payload: dict) -> None:
        price=float(payload.get("normalized_price"));increment=float(payload.get("increment") or 0.0)
        if not payload.get("valid") or increment <= 0 or not is_price_on_increment(price,increment):
            raise ValueError(f"Broker price validation failed before transmission: price={price} increment={increment}")

    def submit_order(self, request: IbkrPaperOrderRequest) -> int:
        request.validate(); app=self._require()
        Contract,Order=self._types(); c=Contract(); c.conId=request.contract_id; c.symbol=request.symbol; c.localSymbol=request.local_symbol; c.secType=request.security_type; c.currency=request.currency; c.exchange=request.exchange; c.primaryExchange=request.primary_exchange; c.lastTradeDateOrContractMonth=request.expiry; c.strike=request.strike or 0; c.right=request.right; c.multiplier=request.multiplier
        o=_normalize_order_compatibility(Order()); o.account=request.broker_account_id; o.action=request.side.upper(); o.totalQuantity=Decimal(str(request.quantity)); o.orderType=request.order_type.upper(); o.tif=request.time_in_force.upper(); o.outsideRth=request.outside_regular_hours; o.transmit=request.transmit; o.orderRef=request.aggregate_id
        validation={"security_type":str(request.security_type).upper(),"aggregate_id":request.aggregate_id}
        if request.limit_price is not None:
            if int(request.contract_id or 0)<=0:
                raise ValueError("Limit order has no qualified IBKR contract_id; refusing to transmit without broker price validation")
            normalized=self.normalize_contract_limit_price(contract_id=request.contract_id,price=float(request.limit_price),side=request.side,exchange=request.exchange)
            self._assert_valid_normalization(normalized);o.lmtPrice=float(normalized["normalized_price"]);validation["limit_price"]=normalized
        if request.stop_price is not None:
            if int(request.contract_id or 0)<=0:
                raise ValueError("Stop order has no qualified IBKR contract_id; refusing to transmit without broker price validation")
            normalized_stop=self.normalize_contract_limit_price(contract_id=request.contract_id,price=float(request.stop_price),side=request.side,exchange=request.exchange)
            self._assert_valid_normalization(normalized_stop);o.auxPrice=float(normalized_stop["normalized_price"]);validation["stop_price"]=normalized_stop
        self._record_outbound_price_validation(request.aggregate_id,validation)
        oid=app.reserve_order_id();app.begin_order_ack(oid)
        LOGGER.info("IBKR placeOrder validated order_id=%s aggregate_id=%s security_type=%s validation=%s", oid, request.aggregate_id, request.security_type, validation)
        app.placeOrder(oid,c,o)
        LOGGER.info("IBKR placeOrder returned order_id=%s; awaiting asynchronous acknowledgement", oid)
        return oid
    def resolve_option_contract(self, *, symbol: str, expiry: str, strike: float, right: str, currency: str = "USD", exchange: str = "SMART", multiplier: str = "100", local_symbol: str = "") -> IbkrPaperComboLegRequest:
        app = self._require()
        Contract, _ = self._types()
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.currency = currency
        contract.exchange = exchange
        contract.lastTradeDateOrContractMonth = expiry.replace("-", "")
        contract.strike = float(strike)
        contract.right = "C" if right.upper() in {"CALL", "C"} else "P"
        contract.multiplier = str(multiplier or "100")
        if local_symbol and not local_symbol.upper().startswith("O:"):
            contract.localSymbol = local_symbol
        request_id = app.next_request_id()
        app.begin_contract_details(request_id)
        app.reqContractDetails(request_id, contract)
        if not app.contract_details_ready[request_id].wait(self._config.timeout_seconds):
            raise TimeoutError(f"IBKR contract resolution timed out for {symbol} {expiry} {right} {strike}")
        rows = app.contract_detail_rows.pop(request_id, [])
        app.contract_details_ready.pop(request_id, None)
        error_text = app.contract_detail_errors.pop(request_id, "")
        if not rows:
            detail = f": {error_text}" if error_text else ""
            raise LookupError(f"IBKR option contract not found for {symbol} {expiry} {right} {strike}{detail}")
        rows.sort(key=lambda row: (0 if row["exchange"] == "SMART" else 1, row["contract_id"]))
        selected = rows[0]
        self._contract_rule_cache[(int(selected["contract_id"]),str(selected.get("exchange") or exchange or "SMART").upper())]=dict(selected)
        return IbkrPaperComboLegRequest(
            contract_id=selected["contract_id"],
            ratio=1,
            action="BUY",
            exchange=selected["exchange"] or exchange,
            symbol=symbol,
            local_symbol=selected["local_symbol"],
            expiry=expiry,
            strike=float(strike),
            right="CALL" if contract.right == "C" else "PUT",
            multiplier=str(selected["multiplier"] or multiplier or "100"),
        )

    def submit_combo_order_prepared(self, request: IbkrPaperComboOrderRequest, *, initial_order_id: int, before_transmit=None) -> int:
        """Submit a BAG with durable pre-transmit lineage supplied by the caller.

        ``initial_order_id`` must already be persisted by the order service.  When
        error 110 requires a new candidate/order id, ``before_transmit`` is invoked
        *before* placeOrder() so the durable broker row can be advanced to that id.
        Only an explicit error 110 advances the bounded candidate grid.
        """
        request.validate();app=self._require();contract=self._build_combo_contract(request)
        attempts=[];last_oid=None
        candidates=self._combo_candidate_normalizations(request)
        for index,normalization in enumerate(candidates, start=1):
            oid=int(initial_order_id) if index==1 else int(app.reserve_order_id());last_oid=oid
            if callable(before_transmit):
                before_transmit(oid, dict(normalization), index, list(attempts))
            app.begin_order_ack(oid)
            order=self._build_combo_order(request,limit_price=float(normalization["normalized_price"]),transmit=bool(request.transmit),order_ref=request.aggregate_id)
            LOGGER.info("IBKR BAG price-grid discovery submit order_id=%s aggregate_id=%s attempt=%s/%s price=%s grid=%s",oid,request.aggregate_id,index,len(candidates),normalization["normalized_price"],normalization.get("increment"))
            app.placeOrder(oid,contract,order)
            ack=self.wait_for_order_acknowledgement(oid)
            attempt={"candidate":dict(normalization),"ack":dict(ack),"broker_order_id":oid,"transmitted":bool(request.transmit)}
            attempts.append(attempt)
            callback=str(ack.get("callback") or "").upper();code=int(ack.get("error_code") or 0) if callback=="ERROR" else 0
            if callback=="ERROR" and code==110:
                LOGGER.warning("IBKR BAG price grid rejected with error 110; advancing aggregate_id=%s order_id=%s price=%s grid=%s",request.aggregate_id,oid,normalization["normalized_price"],normalization.get("increment"))
                continue
            final=dict(normalization)
            final.update({
                "valid": bool(ack.get("acknowledged")) and callback != "ERROR",
                "validation": "IBKR_ACKNOWLEDGED" if bool(ack.get("acknowledged")) else ("IBKR_PRICE_GRID_REJECTED" if callback=="ERROR" else "IBKR_ACK_INCONCLUSIVE"),
                "source":"IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY",
                "broker_order_id":oid,
                "broker_acknowledgement":dict(ack),
                "candidate_attempt_count":len(attempts),
                "candidate_attempts":attempts,
                "durable_pretransmit_lineage":True,
            })
            self._record_outbound_price_validation(request.aggregate_id,{"security_type":"BAG","aggregate_id":request.aggregate_id,"limit_price":final})
            return oid
        if last_oid is None:
            raise RuntimeError("No BAG price-grid candidates were generated")
        final=dict(candidates[-1]);final.update({
            "valid":False,
            "validation":"IBKR_PRICE_GRID_EXHAUSTED",
            "source":"IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY",
            "broker_order_id":last_oid,
            "broker_acknowledgement":dict(attempts[-1]["ack"]),
            "candidate_attempt_count":len(attempts),
            "candidate_attempts":attempts,
            "durable_pretransmit_lineage":True,
        })
        self._record_outbound_price_validation(request.aggregate_id,{"security_type":"BAG","aggregate_id":request.aggregate_id,"limit_price":final})
        return last_oid

    def submit_combo_order(self, request: IbkrPaperComboOrderRequest) -> int:
        """Backward-compatible BAG submission.

        Production order service uses :meth:`submit_combo_order_prepared` so a
        durable broker row exists before transmission. Direct callers retain the
        previous bounded grid behavior.
        """
        initial=self.reserve_order_id()
        return self.submit_combo_order_prepared(request,initial_order_id=initial)

    def prepare_existing_order_for_modify(self, broker_order_id: int) -> dict:
        """Refresh and bind current open-order truth before an in-place modify.

        A new API connection using the same client id can otherwise race TWS order
        ownership/visibility and produce error 103 (Duplicate order id).  Requiring
        the existing order to be visible via reqOpenOrders before placeOrder makes
        the modify fail closed without cancelling the live broker order.
        """
        app=self._require();oid=int(broker_order_id)
        app.begin_orders();app.reqOpenOrders()
        if not app.orders_ready.wait(self._config.timeout_seconds):
            raise TimeoutError(f"IBKR open-order refresh timed out before modifying order {oid}")
        row=dict(app.order_rows.get(oid) or {})
        return {"visible":bool(row),"broker_order_id":oid,"status":str(row.get('status') or ''),"remaining_quantity":float(row.get('remaining_quantity') or 0.0),"client_id":int(row.get('client_id') or 0),"row":row}

    def modify_order(self, broker_order_id: int, request: IbkrPaperOrderRequest) -> int:
        """Modify an existing order only after broker-rule price validation."""
        request.validate();app=self._require();oid=int(broker_order_id)
        Contract,Order=self._types();c=Contract();c.conId=request.contract_id;c.symbol=request.symbol;c.localSymbol=request.local_symbol;c.secType=request.security_type;c.currency=request.currency;c.exchange=request.exchange;c.primaryExchange=request.primary_exchange;c.lastTradeDateOrContractMonth=request.expiry;c.strike=request.strike or 0;c.right=request.right;c.multiplier=request.multiplier
        o=_normalize_order_compatibility(Order());o.account=request.broker_account_id;o.action=request.side.upper();o.totalQuantity=Decimal(str(request.quantity));o.orderType=request.order_type.upper();o.tif=request.time_in_force.upper();o.outsideRth=request.outside_regular_hours;o.transmit=request.transmit;o.orderRef=request.aggregate_id
        validation={"security_type":str(request.security_type).upper(),"aggregate_id":request.aggregate_id,"modify":True}
        if request.limit_price is not None:
            if int(request.contract_id or 0)<=0:raise ValueError("Limit modify has no qualified IBKR contract_id; refusing to transmit")
            normalized=self.normalize_contract_limit_price(contract_id=request.contract_id,price=float(request.limit_price),side=request.side,exchange=request.exchange);self._assert_valid_normalization(normalized);o.lmtPrice=float(normalized["normalized_price"]);validation["limit_price"]=normalized
        if request.stop_price is not None:
            if int(request.contract_id or 0)<=0:raise ValueError("Stop modify has no qualified IBKR contract_id; refusing to transmit")
            normalized_stop=self.normalize_contract_limit_price(contract_id=request.contract_id,price=float(request.stop_price),side=request.side,exchange=request.exchange);self._assert_valid_normalization(normalized_stop);o.auxPrice=float(normalized_stop["normalized_price"]);validation["stop_price"]=normalized_stop
        self._record_outbound_price_validation(request.aggregate_id,validation);app.begin_order_ack(oid);app.placeOrder(oid,c,o);return oid

    def modify_combo_order(self, broker_order_id: int, request: IbkrPaperComboOrderRequest) -> int:
        """Modify a BAG with bounded error-110 price-grid discovery.

        The existing broker order id is retained.  We only try the next candidate
        after an explicit error 110.  A timeout or any other callback stops the
        loop immediately, preserving the last known broker order state.
        """
        request.validate();app=self._require();oid=int(broker_order_id);contract=self._build_combo_contract(request);attempts=[]
        candidates=self._combo_candidate_normalizations(request)
        for index,normalization in enumerate(candidates, start=1):
            app.begin_order_ack(oid)
            order=self._build_combo_order(request,limit_price=float(normalization["normalized_price"]),transmit=bool(request.transmit),order_ref=request.aggregate_id)
            LOGGER.info("IBKR BAG modify price-grid discovery order_id=%s aggregate_id=%s attempt=%s/%s price=%s grid=%s",oid,request.aggregate_id,index,len(candidates),normalization["normalized_price"],normalization.get("increment"))
            app.placeOrder(oid,contract,order)
            ack=self.wait_for_order_acknowledgement(oid)
            attempts.append({"candidate":dict(normalization),"ack":dict(ack),"broker_order_id":oid,"modify":True})
            callback=str(ack.get("callback") or "").upper();code=int(ack.get("error_code") or 0) if callback=="ERROR" else 0
            if callback=="ERROR" and code==110:
                continue
            final=dict(normalization);final.update({"valid":bool(ack.get("acknowledged")) and callback!="ERROR","validation":"IBKR_ACKNOWLEDGED" if bool(ack.get("acknowledged")) else ("IBKR_PRICE_GRID_REJECTED" if callback=="ERROR" else "IBKR_ACK_INCONCLUSIVE"),"source":"IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY","broker_order_id":oid,"broker_acknowledgement":dict(ack),"candidate_attempt_count":len(attempts),"candidate_attempts":attempts})
            self._record_outbound_price_validation(request.aggregate_id,{"security_type":"BAG","aggregate_id":request.aggregate_id,"modify":True,"limit_price":final})
            return oid
        final=dict(candidates[-1]);final.update({"valid":False,"validation":"IBKR_PRICE_GRID_EXHAUSTED","source":"IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY","broker_order_id":oid,"broker_acknowledgement":dict(attempts[-1]["ack"]),"candidate_attempt_count":len(attempts),"candidate_attempts":attempts})
        self._record_outbound_price_validation(request.aggregate_id,{"security_type":"BAG","aggregate_id":request.aggregate_id,"modify":True,"limit_price":final})
        return oid

    def wait_for_order_acknowledgement(self, broker_order_id: int, timeout_seconds: float | None = None) -> dict:
        app = self._require()
        timeout = float(timeout_seconds if timeout_seconds is not None else self._config.timeout_seconds)
        event = app.order_ack_events.get(int(broker_order_id))
        if event is None:
            raise RuntimeError(f"IBKR acknowledgement tracker missing for order {broker_order_id}")
        if not event.wait(timeout):
            payload = {
                "acknowledged": False,
                "callback": "TIMEOUT",
                "status": "AWAITING_BROKER_ACK",
                "broker_order_id": int(broker_order_id),
                "received_at": utc_now_iso(),
            }
            app.order_ack_payloads[int(broker_order_id)] = payload
            return payload
        return dict(app.order_ack_payloads.get(int(broker_order_id)) or {
            "acknowledged": False,
            "callback": "UNKNOWN",
            "status": "AWAITING_BROKER_ACK",
            "broker_order_id": int(broker_order_id),
            "received_at": utc_now_iso(),
        })

    def cancel_order(self, broker_order_id: int) -> None:
        """Request broker cancellation; terminal truth is confirmed separately.

        The caller must use :meth:`wait_for_cancel_terminal` before treating the
        order as cancelled.  This deliberately separates local cancellation
        intent from IBKR terminal acknowledgement.
        """
        app = self._require()
        order_id = int(broker_order_id)
        # Reset the acknowledgement tracker so a stale submission callback cannot
        # be mistaken for the cancellation acknowledgement.
        app.begin_order_ack(order_id)
        try:
            app.cancelOrder(order_id)
        except TypeError:
            app.cancelOrder(order_id, "")

    def wait_for_cancel_terminal(self, broker_order_id: int, permanent_id: int = 0, timeout_seconds: float | None = None) -> dict:
        """Wait for broker-confirmed cancellation/fill/rejection after cancel.

        Cancellation can race a fill, and cancelled orders may disappear from
        reqOpenOrders immediately.  We therefore observe live orderStatus
        callbacks first, then consult completed-order history and match by
        permanent id when the transient order id is absent.
        """
        app = self._require()
        order_id = int(broker_order_id)
        perm_id = int(permanent_id or 0)
        timeout = float(timeout_seconds if timeout_seconds is not None else self._config.timeout_seconds)
        deadline = time.monotonic() + max(0.05, timeout)
        terminal = {"CANCELLED", "CANCELED", "APICANCELLED", "FILLED", "INACTIVE", "REJECTED"}

        def normalized(row: dict | None, source: str) -> dict | None:
            if not row:
                return None
            status = str(row.get("status") or "").upper().replace(" ", "")
            if status not in terminal:
                return None
            return {
                "terminal_confirmed": True,
                "broker_order_id": int(row.get("broker_order_id") or order_id),
                "permanent_id": int(row.get("permanent_id") or perm_id),
                "status": str(row.get("status") or status),
                "filled_quantity": float(row.get("filled_quantity") or 0.0),
                "remaining_quantity": float(row.get("remaining_quantity") or 0.0),
                "average_fill_price": float(row.get("average_fill_price") or 0.0),
                "source": source,
                "raw": dict(row.get("raw") or {}),
            }

        while time.monotonic() < deadline:
            direct = normalized(app.order_rows.get(order_id), "ORDER_STATUS")
            if direct:
                return direct
            if perm_id:
                for row in app.order_rows.values():
                    if int(row.get("permanent_id") or 0) == perm_id:
                        match = normalized(row, "ORDER_STATUS_PERMANENT_ID")
                        if match:
                            return match
            time.sleep(0.05)

        request_completed = getattr(app, "reqCompletedOrders", None)
        if callable(request_completed):
            app.begin_completed_orders()
            request_completed(False)
            remaining = max(0.05, min(timeout, 2.0))
            if app.completed_orders_ready.wait(remaining):
                rows = list(app.completed_order_rows.values())
                for row in rows:
                    if int(row.get("broker_order_id") or 0) == order_id:
                        match = normalized(row, "COMPLETED_ORDERS")
                        if match:
                            return match
                if perm_id:
                    for row in rows:
                        if int(row.get("permanent_id") or 0) == perm_id:
                            match = normalized(row, "COMPLETED_ORDERS_PERMANENT_ID")
                            if match:
                                return match

        return {
            "terminal_confirmed": False,
            "broker_order_id": order_id,
            "permanent_id": perm_id,
            "status": "CANCEL_REQUESTED",
            "source": "TIMEOUT",
        }
    def order_statuses(self, account_id: str):
        """
        Return both active and terminal IBKR order states.

        reqOpenOrders() only reports currently working API orders. Orders that
        were filled, canceled, API-canceled, or rejected can disappear from
        that result immediately. reqCompletedOrders(False) supplies those
        terminal rows so database reconciliation can close canonical orders.
        """
        app = self._require()

        app.begin_orders()
        app.reqOpenOrders()
        if not app.orders_ready.wait(self._config.timeout_seconds):
            raise TimeoutError("IBKR open-order request timed out")

        combined = dict(app.order_rows)

        # Completed-order support is available on current IBKR API versions,
        # but preserve compatibility with older clients by treating it as an
        # optional enrichment rather than failing active-order reconciliation.
        request_completed = getattr(app, "reqCompletedOrders", None)
        if callable(request_completed):
            app.begin_completed_orders()
            request_completed(False)
            if not app.completed_orders_ready.wait(self._config.timeout_seconds):
                raise TimeoutError("IBKR completed-order request timed out")
            combined.update(app.completed_order_rows)

        return [IbkrPaperOrderStatus(**row) for row in combined.values()]
    def executions(self, account_id: str):
        app=self._require(); app.begin_exec(); _,ExecutionFilter=self._types(extra=True); f=ExecutionFilter(); f.acctCode=account_id; req=app.next_request_id(); app.reqExecutions(req,f)
        if not app.exec_ready.wait(self._config.timeout_seconds): raise TimeoutError("IBKR execution request timed out")
        return list(app.execution_rows.values())
    def _require(self):
        if self._app is None or not self._app.isConnected(): raise RuntimeError("IBKR transport is not connected")
        return self._app
    @staticmethod
    def _types(extra=False):
        from ibapi.contract import Contract
        from ibapi.order import Order
        if extra:
            from ibapi.execution import ExecutionFilter
            return Contract,ExecutionFilter
        return Contract,Order
    @staticmethod
    def _build_app():
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        class App(EWrapper,EClient):
            def __init__(self):
                EClient.__init__(self,self); self.api_ready=threading.Event(); self.accounts_ready=threading.Event(); self.orders_ready=threading.Event(); self.completed_orders_ready=threading.Event(); self.exec_ready=threading.Event(); self.managed_accounts=set(); self.next_id=None; self.order_rows={}; self.completed_order_rows={}; self.execution_rows={}; self.contract_detail_rows={}; self.contract_details_ready={}; self.contract_detail_errors={}; self.market_rule_rows={}; self.market_rule_ready={}; self.order_ack_events={}; self.order_ack_payloads={}; self._req=10000
            def begin_order_ack(self, order_id):
                oid = int(order_id)
                self.order_ack_events[oid] = threading.Event()
                self.order_ack_payloads.pop(oid, None)
            def record_order_ack(self, order_id, payload):
                oid = int(order_id)
                body = {**payload, "broker_order_id": oid, "received_at": utc_now_iso()}
                self.order_ack_payloads[oid] = body
                event = self.order_ack_events.get(oid)
                if event is not None:
                    event.set()
            def nextValidId(self,orderId): self.next_id=int(orderId); self.api_ready.set()
            def reserve_order_id(self):
                if self.next_id is None: raise RuntimeError("IBKR order id unavailable")
                value=self.next_id; self.next_id += 1; return value
            def next_request_id(self): self._req += 1; return self._req
            def begin_contract_details(self, request_id):
                self.contract_detail_rows[request_id] = []
                self.contract_details_ready[request_id] = threading.Event()
                self.contract_detail_errors.pop(request_id, None)
            def contractDetails(self, reqId, contractDetails):
                contract = contractDetails.contract
                self.contract_detail_rows.setdefault(int(reqId), []).append({
                    "contract_id": int(getattr(contract, "conId", 0) or 0),
                    "local_symbol": str(getattr(contract, "localSymbol", "") or ""),
                    "exchange": str(getattr(contract, "exchange", "") or "SMART"),
                    "multiplier": str(getattr(contract, "multiplier", "") or "100"),
                    "trading_class": str(getattr(contract, "tradingClass", "") or ""),
                    "min_tick": float(getattr(contractDetails, "minTick", 0.0) or 0.0),
                    "valid_exchanges": str(getattr(contractDetails, "validExchanges", "") or ""),
                    "market_rule_ids": str(getattr(contractDetails, "marketRuleIds", "") or ""),
                })
            def contractDetailsEnd(self, reqId):
                event = self.contract_details_ready.get(int(reqId))
                if event is not None:
                    event.set()
            def begin_market_rule(self, market_rule_id):
                rule_id=int(market_rule_id); self.market_rule_rows[rule_id]=[]; self.market_rule_ready[rule_id]=threading.Event()
            def marketRule(self, marketRuleId, priceIncrements):
                rule_id=int(marketRuleId); self.market_rule_rows[rule_id]=[{"low_edge":float(getattr(x,"lowEdge",0.0) or 0.0),"increment":float(getattr(x,"increment",0.0) or 0.0)} for x in (priceIncrements or [])]
                event=self.market_rule_ready.get(rule_id)
                if event is not None:event.set()
            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
                if int(reqId) in self.contract_details_ready:
                    self.contract_detail_errors[int(reqId)] = f"{errorCode}: {errorString}"
                    if int(errorCode) in {200, 321, 322}:
                        self.contract_details_ready[int(reqId)].set()
            def managedAccounts(self,accountsList): self.managed_accounts={a.strip().upper() for a in accountsList.split(',') if a.strip()}; self.accounts_ready.set()
            def begin_orders(self): self.order_rows={}; self.orders_ready.clear()
            def openOrder(self,orderId,contract,order,orderState):
                status = str(getattr(orderState,'status','Submitted') or 'Submitted')
                perm_id = int(getattr(order,'permId',0) or 0)
                self.order_rows.setdefault(int(orderId),{"broker_order_id":int(orderId),"permanent_id":perm_id,"client_id":int(getattr(order,'clientId',0) or 0),"status":status,"filled_quantity":0.0,"remaining_quantity":float(order.totalQuantity),"average_fill_price":0.0,"raw":{"symbol":contract.symbol}})
                self.record_order_ack(orderId, {"acknowledged": True, "callback": "OPEN_ORDER", "status": status.upper().replace(" ", "_"), "permanent_id": perm_id})
            def orderStatus(self,orderId,status,filled,remaining,avgFillPrice,permId,parentId,lastFillPrice,clientId,whyHeld,mktCapPrice=0):
                self.order_rows[int(orderId)]={"broker_order_id":int(orderId),"permanent_id":int(permId or 0),"client_id":int(clientId or 0),"status":status,"filled_quantity":float(filled),"remaining_quantity":float(remaining),"average_fill_price":float(avgFillPrice),"last_fill_price":float(lastFillPrice),"why_held":whyHeld or "","updated_at":utc_now_iso(),"raw":{"parent_id":parentId}}
                self.record_order_ack(orderId, {"acknowledged": True, "callback": "ORDER_STATUS", "status": str(status).upper().replace(" ", "_"), "permanent_id": int(permId or 0), "filled_quantity": float(filled), "remaining_quantity": float(remaining), "average_fill_price": float(avgFillPrice), "why_held": whyHeld or ""})
            def openOrderEnd(self): self.orders_ready.set()
            def begin_completed_orders(self):
                self.completed_order_rows={}
                self.completed_orders_ready.clear()
            def completedOrder(self,contract,order,orderState):
                order_id=int(getattr(order,'orderId',0) or 0)
                permanent_id=int(getattr(order,'permId',0) or 0)
                if order_id <= 0 and permanent_id <= 0:
                    return
                total=float(getattr(order,'totalQuantity',0.0) or 0.0)
                filled=float(getattr(orderState,'filledQuantity',0.0) or 0.0)
                remaining=max(0.0,total-filled)
                status=str(getattr(orderState,'status','') or 'Completed')
                completed_key = order_id if order_id > 0 else f"perm:{permanent_id}"
                self.completed_order_rows[completed_key]={
                    "broker_order_id":order_id,
                    "permanent_id":permanent_id,
                    "client_id":int(getattr(order,'clientId',0) or 0),
                    "status":status,
                    "filled_quantity":filled,
                    "remaining_quantity":remaining,
                    "average_fill_price":0.0,
                    "updated_at":utc_now_iso(),
                    "raw":{
                        "symbol":getattr(contract,'symbol',''),
                        "completed_time":str(getattr(orderState,'completedTime','') or ''),
                        "completed_status":str(getattr(orderState,'completedStatus','') or ''),
                        "source":"COMPLETED_ORDERS",
                    },
                }
            def completedOrdersEnd(self): self.completed_orders_ready.set()
            def begin_exec(self): self.execution_rows={}; self.exec_ready.clear()
            def execDetails(self,reqId,contract,execution):
                self.execution_rows[execution.execId]=IbkrPaperExecution(execution_id=execution.execId,broker_order_id=int(execution.orderId),permanent_id=int(execution.permId or 0),client_id=int(execution.clientId or 0),broker_account_id=execution.acctNumber,contract_id=int(contract.conId or 0),symbol=contract.symbol,security_type=contract.secType,side=execution.side,quantity=float(execution.shares),price=float(execution.price),commission=0.0,currency=contract.currency or 'USD',executed_at=execution.time,exchange=execution.exchange or '',liquidation=int(execution.liquidation or 0),raw={"order_ref":execution.orderRef})
            def execDetailsEnd(self,reqId): self.exec_ready.set()
            def error(self,reqId,errorCode,errorString,advancedOrderRejectJson=''):
                code = int(errorCode)
                request_id = int(reqId)
                if request_id in self.contract_details_ready:
                    self.contract_detail_errors[request_id] = f"{code}: {errorString}"
                    if code in {200, 321, 322}:
                        self.contract_details_ready[request_id].set()
                if request_id in self.market_rule_ready:
                    event=self.market_rule_ready.get(request_id)
                    if event is not None:event.set()
                if code in {2104,2106,2107,2108,2158}:
                    return
                if request_id in self.order_ack_events:
                    message = str(errorString or '')
                    LOGGER.error("IBKR callback error order_id=%s code=%s message=%s reject_json=%s", request_id, code, message, advancedOrderRejectJson or '')
                    self.record_order_ack(request_id, {"acknowledged": False, "callback": "ERROR", "status": "REJECTED", "error_code": code, "error_message": message, "advanced_order_reject_json": advancedOrderRejectJson or ''})
                if code in {502,503,504,1100,1300}:
                    self.api_ready.set(); self.accounts_ready.set(); self.orders_ready.set(); self.completed_orders_ready.set(); self.exec_ready.set()
        return App()
