from __future__ import annotations
import threading
from decimal import Decimal
from typing import Any
from .models import IbkrPaperConnectionConfig
from .order_models import IbkrPaperExecution, IbkrPaperOrderRequest, IbkrPaperOrderStatus, utc_now_iso

class IbapiPaperOrderTransport:
    def __init__(self): self._app=None; self._config=None; self._thread=None
    def connect(self, config: IbkrPaperConnectionConfig):
        config.validate()
        app=self._build_app(); app.connect(config.host,config.port,clientId=config.client_id)
        thread=threading.Thread(target=app.run,daemon=True); thread.start()
        if not app.api_ready.wait(config.timeout_seconds): app.disconnect(); raise TimeoutError("IBKR API readiness timed out")
        if not app.accounts_ready.is_set(): app.reqManagedAccts()
        if not app.accounts_ready.wait(config.timeout_seconds): app.disconnect(); raise TimeoutError("IBKR account discovery timed out")
        accounts=tuple(sorted(app.managed_accounts))
        if config.expected_account_id.upper() not in accounts: app.disconnect(); raise RuntimeError("registered paper account not exposed")
        if any(not a.startswith("DU") for a in accounts): app.disconnect(); raise RuntimeError("non-paper managed account rejected")
        self._app=app; self._config=config; self._thread=thread
        return {"status":"CONNECTED_PAPER_ORDER_CAPABLE","managed_accounts":accounts,"server_version":app.serverVersion(),"live_trading_enabled":False}
    def disconnect(self):
        if self._app is not None: self._app.disconnect()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=2)
        self._app=None; self._config=None; self._thread=None
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

    def submit_order(self, request: IbkrPaperOrderRequest) -> int:
        request.validate(); app=self._require(); oid=app.reserve_order_id()
        Contract,Order=self._types(); c=Contract(); c.conId=request.contract_id; c.symbol=request.symbol; c.localSymbol=request.local_symbol; c.secType=request.security_type; c.currency=request.currency; c.exchange=request.exchange; c.primaryExchange=request.primary_exchange; c.lastTradeDateOrContractMonth=request.expiry; c.strike=request.strike or 0; c.right=request.right; c.multiplier=request.multiplier
        o=Order(); o.account=request.broker_account_id; o.action=request.side.upper(); o.totalQuantity=Decimal(str(request.quantity)); o.orderType=request.order_type.upper(); o.tif=request.time_in_force.upper(); o.outsideRth=request.outside_regular_hours; o.transmit=request.transmit; o.orderRef=request.aggregate_id
        if request.limit_price is not None: o.lmtPrice=float(request.limit_price)
        if request.stop_price is not None: o.auxPrice=float(request.stop_price)
        app.placeOrder(oid,c,o); return oid
    def cancel_order(self, broker_order_id: int) -> None:
        """
        Cancel an IBKR order across ibapi client versions.

        Older ibapi releases expose cancelOrder(orderId), while newer releases
        may accept an additional manual-cancel-time argument. Calling the
        one-argument form first is compatible with the installed legacy API;
        if a newer client requires the second argument, retry with an empty
        manual-cancel-time value.
        """
        app = self._require()
        order_id = int(broker_order_id)
        try:
            app.cancelOrder(order_id)
        except TypeError:
            app.cancelOrder(order_id, "")
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
                EClient.__init__(self,self); self.api_ready=threading.Event(); self.accounts_ready=threading.Event(); self.orders_ready=threading.Event(); self.completed_orders_ready=threading.Event(); self.exec_ready=threading.Event(); self.managed_accounts=set(); self.next_id=None; self.order_rows={}; self.completed_order_rows={}; self.execution_rows={}; self._req=10000
            def nextValidId(self,orderId): self.next_id=int(orderId); self.api_ready.set()
            def reserve_order_id(self):
                if self.next_id is None: raise RuntimeError("IBKR order id unavailable")
                value=self.next_id; self.next_id += 1; return value
            def next_request_id(self): self._req += 1; return self._req
            def managedAccounts(self,accountsList): self.managed_accounts={a.strip().upper() for a in accountsList.split(',') if a.strip()}; self.accounts_ready.set()
            def begin_orders(self): self.order_rows={}; self.orders_ready.clear()
            def openOrder(self,orderId,contract,order,orderState):
                self.order_rows.setdefault(int(orderId),{"broker_order_id":int(orderId),"permanent_id":int(getattr(order,'permId',0) or 0),"client_id":int(getattr(order,'clientId',0) or 0),"status":str(getattr(orderState,'status','Submitted') or 'Submitted'),"filled_quantity":0.0,"remaining_quantity":float(order.totalQuantity),"average_fill_price":0.0,"raw":{"symbol":contract.symbol}})
            def orderStatus(self,orderId,status,filled,remaining,avgFillPrice,permId,parentId,lastFillPrice,clientId,whyHeld,mktCapPrice=0):
                self.order_rows[int(orderId)]={"broker_order_id":int(orderId),"permanent_id":int(permId or 0),"client_id":int(clientId or 0),"status":status,"filled_quantity":float(filled),"remaining_quantity":float(remaining),"average_fill_price":float(avgFillPrice),"last_fill_price":float(lastFillPrice),"why_held":whyHeld or "","updated_at":utc_now_iso(),"raw":{"parent_id":parentId}}
            def openOrderEnd(self): self.orders_ready.set()
            def begin_completed_orders(self):
                self.completed_order_rows={}
                self.completed_orders_ready.clear()
            def completedOrder(self,contract,order,orderState):
                order_id=int(getattr(order,'orderId',0) or 0)
                if order_id <= 0:
                    return
                total=float(getattr(order,'totalQuantity',0.0) or 0.0)
                filled=float(getattr(orderState,'filledQuantity',0.0) or 0.0)
                remaining=max(0.0,total-filled)
                status=str(getattr(orderState,'status','') or 'Completed')
                self.completed_order_rows[order_id]={
                    "broker_order_id":order_id,
                    "permanent_id":int(getattr(order,'permId',0) or 0),
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
                if errorCode in {2104,2106,2107,2108,2158}: return
                if errorCode in {502,503,504,1100,1300}: self.api_ready.set(); self.accounts_ready.set(); self.orders_ready.set(); self.completed_orders_ready.set(); self.exec_ready.set()
        return App()
