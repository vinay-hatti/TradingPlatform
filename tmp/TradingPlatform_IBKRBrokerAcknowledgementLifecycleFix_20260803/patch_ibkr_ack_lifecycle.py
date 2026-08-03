from __future__ import annotations
from pathlib import Path
import re, shutil, sys, time


def replace_method(text: str, name: str, replacement: str, *, occurrence: int = 1) -> str:
    pat = re.compile(rf'(?m)^(?P<indent>[ \t]*)def {re.escape(name)}\([^\n]*\)(?:\s*->\s*[^:]+)?:\n')
    matches=list(pat.finditer(text))
    if len(matches)<occurrence:
        raise RuntimeError(f'method {name} occurrence {occurrence} not found')
    m=matches[occurrence-1]; indent=m.group('indent'); start=m.start()
    lines=text[m.end():].splitlines(True); pos=m.end()
    for line in lines:
        if line.strip() and len(line)-len(line.lstrip()) <= len(indent) and not line.lstrip().startswith(('#','@')):
            break
        pos += len(line)
    repl='\n'.join(indent+ln if ln else '' for ln in replacement.strip('\n').split('\n'))+'\n'
    return text[:start]+repl+text[pos:]


def apply(root: Path, backup: Path):
    tpath=root/'src/trading_ai/broker/ibkr/order_transport.py'
    spath=root/'src/trading_ai/broker/ibkr/order_service.py'
    for p in (tpath,spath):
        if not p.exists(): raise FileNotFoundError(p)
        dest=backup/p.relative_to(root); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest)

    text=tpath.read_text()
    if 'import logging' not in text:
        text=text.replace('import threading\n','import threading\nimport logging\n')
    if 'LOGGER = logging.getLogger(__name__)' not in text:
        anchor='from .order_models import IbkrPaperExecution, IbkrPaperOrderRequest, IbkrPaperOrderStatus, utc_now_iso\n'
        text=text.replace(anchor,anchor+'\nLOGGER = logging.getLogger(__name__)\n')

    text=replace_method(text,'submit_order','''def submit_order(self, request: IbkrPaperOrderRequest) -> int:
    request.validate()
    app = self._require()
    oid = app.reserve_order_id()
    Contract, Order = self._types()
    c = Contract()
    c.conId = request.contract_id
    c.symbol = request.symbol
    c.localSymbol = request.local_symbol
    c.secType = request.security_type
    c.currency = request.currency
    c.exchange = request.exchange
    c.primaryExchange = request.primary_exchange
    c.lastTradeDateOrContractMonth = request.expiry
    c.strike = request.strike or 0
    c.right = request.right
    c.multiplier = request.multiplier
    o = Order()
    o.account = request.broker_account_id
    o.action = request.side.upper()
    o.totalQuantity = Decimal(str(request.quantity))
    o.orderType = request.order_type.upper()
    o.tif = request.time_in_force.upper()
    o.outsideRth = request.outside_regular_hours
    o.transmit = request.transmit
    o.orderRef = request.aggregate_id
    if request.limit_price is not None:
        o.lmtPrice = float(request.limit_price)
    if request.stop_price is not None:
        o.auxPrice = float(request.stop_price)
    app.begin_order_submission(oid)
    LOGGER.info("IBKR placeOrder sending order_id=%s aggregate_id=%s security_type=%s", oid, request.aggregate_id, request.security_type)
    app.placeOrder(oid, c, o)
    LOGGER.info("IBKR placeOrder returned order_id=%s; awaiting asynchronous acknowledgement", oid)
    return oid''')

    insert='''\n    def await_order_acknowledgement(self, broker_order_id: int, timeout_seconds: float | None = None) -> dict:\n        app = self._require()\n        timeout = float(timeout_seconds if timeout_seconds is not None else self._config.timeout_seconds)\n        return app.wait_for_order_acknowledgement(int(broker_order_id), timeout)\n'''
    if 'def await_order_acknowledgement' not in text:
        marker='    def cancel_order(self, broker_order_id: int) -> None:\n'
        text=text.replace(marker,insert+'\n'+marker)

    # Expand App.__init__ state without replacing combo-specific code elsewhere.
    old='self.execution_rows={}; self._req=10000'
    new='self.execution_rows={}; self._req=10000; self.order_ack_events={}; self.order_ack_payloads={}; self.order_errors={}; self._order_ack_lock=threading.Lock()'
    if old in text: text=text.replace(old,new)
    elif 'self.order_ack_events' not in text: raise RuntimeError('App initialization marker not found')

    if 'def begin_order_submission' not in text:
        marker='            def next_request_id(self): self._req += 1; return self._req\n'
        addition='''            def begin_order_submission(self, order_id):
                oid=int(order_id)
                with self._order_ack_lock:
                    self.order_ack_events[oid]=threading.Event()
                    self.order_ack_payloads.pop(oid,None)
                    self.order_errors.pop(oid,None)
            def _signal_order_ack(self, order_id, payload):
                oid=int(order_id)
                with self._order_ack_lock:
                    self.order_ack_payloads[oid]=payload
                    event=self.order_ack_events.setdefault(oid,threading.Event())
                    event.set()
            def wait_for_order_acknowledgement(self, order_id, timeout_seconds):
                oid=int(order_id)
                with self._order_ack_lock:
                    event=self.order_ack_events.setdefault(oid,threading.Event())
                received=event.wait(max(0.1,float(timeout_seconds)))
                with self._order_ack_lock:
                    payload=dict(self.order_ack_payloads.get(oid) or {})
                    error=dict(self.order_errors.get(oid) or {})
                if not received:
                    return {"acknowledged":False,"status":"AWAITING_BROKER_ACK","broker_order_id":oid,"permanent_id":0,"error":"","callback":"TIMEOUT","received_at":utc_now_iso()}
                if error:
                    return {"acknowledged":False,"status":"REJECTED","broker_order_id":oid,"permanent_id":0,"error":error.get("message","") or f"IBKR error {error.get('code')}","error_code":error.get("code"),"advanced_reject":error.get("advanced_reject","") or "","callback":"ERROR","received_at":error.get("received_at",utc_now_iso())}
                status=str(payload.get("status") or "ACKNOWLEDGED").upper().replace(" ","_")
                return {"acknowledged":True,"status":status,"broker_order_id":oid,"permanent_id":int(payload.get("permanent_id") or 0),"error":"","callback":payload.get("callback","ORDER_STATUS"),"received_at":payload.get("received_at",utc_now_iso()),"raw":payload.get("raw",{})}
'''
        text=text.replace(marker,marker+addition)

    # Signal callbacks while preserving existing row construction.
    if '"callback":"OPEN_ORDER"' not in text:
        text=text.replace("self.order_rows.setdefault(int(orderId),{\"broker_order_id\"", "self._signal_order_ack(int(orderId),{\"status\":str(getattr(orderState,'status','Submitted') or 'Submitted'),\"permanent_id\":int(getattr(order,'permId',0) or 0),\"callback\":\"OPEN_ORDER\",\"received_at\":utc_now_iso(),\"raw\":{\"symbol\":contract.symbol}}); self.order_rows.setdefault(int(orderId),{\"broker_order_id\"")
    if '"callback":"ORDER_STATUS"' not in text:
        text=text.replace('def orderStatus(self,orderId,status,filled,remaining,avgFillPrice,permId,parentId,lastFillPrice,clientId,whyHeld,mktCapPrice=0):\n                self.order_rows[int(orderId)]', 'def orderStatus(self,orderId,status,filled,remaining,avgFillPrice,permId,parentId,lastFillPrice,clientId,whyHeld,mktCapPrice=0):\n                self._signal_order_ack(int(orderId),{"status":status,"permanent_id":int(permId or 0),"callback":"ORDER_STATUS","received_at":utc_now_iso(),"raw":{"filled":float(filled),"remaining":float(remaining),"why_held":whyHeld or ""}})\n                self.order_rows[int(orderId)]')

    text=replace_method(text,'error','''def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):
    if errorCode in {2104,2106,2107,2108,2158}:
        return
    LOGGER.error("IBKR callback error req_id=%s code=%s message=%s advanced=%s", reqId, errorCode, errorString, advancedOrderRejectJson)
    if int(reqId) >= 0:
        oid=int(reqId)
        with self._order_ack_lock:
            self.order_errors[oid]={"code":int(errorCode),"message":str(errorString),"advanced_reject":str(advancedOrderRejectJson or ''),"received_at":utc_now_iso()}
            event=self.order_ack_events.setdefault(oid,threading.Event())
            event.set()
    if errorCode in {502,503,504,1100,1300}:
        self.api_ready.set()
        self.accounts_ready.set()
        self.orders_ready.set()
        self.completed_orders_ready.set()
        self.exec_ready.set()''', occurrence=1)
    tpath.write_text(text)

    service=spath.read_text()
    old='broker_order_id=int(self.transport.submit_order(request)); now=_now()'
    new='''broker_order_id=int(self.transport.submit_order(request))
            wait_for_ack=getattr(self.transport,"await_order_acknowledgement",None)
            if callable(wait_for_ack):
                acknowledgement=wait_for_ack(broker_order_id)
            else:
                acknowledgement={"acknowledged":True,"status":"SUBMITTED","broker_order_id":broker_order_id,"permanent_id":0,"error":"","callback":"LEGACY_TRANSPORT"}
            now=_now()'''
    if old not in service and 'acknowledgement=wait_for_ack' not in service:
        raise RuntimeError('submit acknowledgement insertion marker not found')
    service=service.replace(old,new)

    row_old='status="SUBMITTED",filled_quantity=0.0,remaining_quantity=request.quantity,average_fill_price=0.0,submitted_at=now,updated_at=now,raw_json={"request":request.__dict__,"paper_only":True}'
    row_new='status=str(acknowledgement.get("status") or "AWAITING_BROKER_ACK").upper(),filled_quantity=0.0,remaining_quantity=request.quantity,average_fill_price=0.0,submitted_at=now,updated_at=now,last_error=str(acknowledgement.get("error") or ""),raw_json={"request":request.__dict__,"paper_only":True,"broker_acknowledgement":acknowledgement}'
    if row_old in service: service=service.replace(row_old,row_new)
    elif 'broker_acknowledgement' not in service: raise RuntimeError('BrokerOrderModel marker not found')

    can_old='canonical.broker_order_id=str(broker_order_id); canonical.state="SUBMITTED"; canonical.updated_at=now; canonical.metadata_json={**(canonical.metadata_json or {}),"broker":"INTERACTIVE_BROKERS","environment":"PAPER"}'
    can_new='''canonical.broker_order_id=str(broker_order_id)
            canonical.state="REJECTED" if str(acknowledgement.get("status","")).upper()=="REJECTED" else "SUBMITTED"
            canonical.updated_at=now
            canonical.metadata_json={**(canonical.metadata_json or {}),"broker":"INTERACTIVE_BROKERS","environment":"PAPER","broker_acknowledgement":acknowledgement}
            if canonical.state=="REJECTED": canonical.terminal_at=canonical.terminal_at or now'''
    if can_old in service: service=service.replace(can_old,can_new)
    elif 'broker_acknowledgement":acknowledgement' not in service: raise RuntimeError('canonical marker not found')

    # Include persisted acknowledgement in API response.
    dict_old='"live_trading_enabled":False}'
    dict_new='"live_trading_enabled":False,"broker_acknowledgement":(row.raw_json or {}).get("broker_acknowledgement",{}),"last_error":row.last_error}'
    service=service.replace(dict_old,dict_new)
    spath.write_text(service)

    # Optional UI compatibility enhancements.
    upath=root/'ui/workstation/src/ExecutionWorkspacePage.tsx'
    if upath.exists():
        dest=backup/upath.relative_to(root); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(upath,dest)
        ui=upath.read_text()
        ui=ui.replace("'CANCEL_REQUESTED'])", "'CANCEL_REQUESTED','AWAITING_BROKER_ACK'])")
        ui=ui.replace("'CANCEL_REQUESTED'].includes", "'CANCEL_REQUESTED','AWAITING_BROKER_ACK'].includes")
        ui=ui.replace("<option value=\"SUBMITTED\">Submitted</option>", "<option value=\"AWAITING_BROKER_ACK\">Awaiting broker acknowledgement</option><option value=\"SUBMITTED\">Submitted</option>")
        upath.write_text(ui)


def main():
    if len(sys.argv)!=2: raise SystemExit('usage: patch_ibkr_ack_lifecycle.py ROOT')
    root=Path(sys.argv[1]).resolve(); stamp=time.strftime('%Y%m%dT%H%M%S')
    backup=root/'backups'/f'ibkr_broker_ack_lifecycle_{stamp}'
    apply(root,backup)
    print(f'Applied IBKR broker acknowledgement lifecycle fix. Backup: {backup}')
if __name__=='__main__': main()
