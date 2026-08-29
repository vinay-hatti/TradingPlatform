from pathlib import Path

SRC=Path('src/trading_ai/broker/ibkr/order_transport.py').read_text()

def _section(name, next_name):
    a=SRC.index(f'def {name}')
    b=SRC.index(f'def {next_name}', a)
    return SRC[a:b]

def test_combo_submission_no_longer_depends_on_transmit_false_staging():
    block=_section('submit_combo_order','prepare_existing_order_for_modify')
    assert 'validate_combo_limit_price' not in block
    assert 'transmit=False' not in block
    assert 'IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY' in block

def test_only_explicit_error_110_advances_price_grid():
    block=_section('submit_combo_order','prepare_existing_order_for_modify')
    assert 'callback=="ERROR" and code==110' in block
    assert 'continue' in block
    assert 'IBKR_ACK_INCONCLUSIVE' in block
    assert 'candidate_attempt_count' in block

def test_combo_modify_uses_same_bounded_error_110_rule():
    block=_section('modify_combo_order','wait_for_order_acknowledgement')
    assert 'callback=="ERROR" and code==110' in block
    assert 'IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY' in block
    assert 'validate_combo_limit_price' not in block

def test_candidate_grids_remain_bounded_and_configurable():
    assert 'TRADING_AI_IBKR_COMBO_PRICE_INCREMENT_CANDIDATES' in SRC
    assert '0.01,0.05,0.10,0.25,0.50,1.00' in SRC
    assert 'normalize_signed_combo_price' in SRC

def test_transmitted_discovery_advances_only_after_explicit_110(monkeypatch):
    from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
    class App:
        def __init__(self): self.next=40; self.placed=[]
        def reserve_order_id(self): self.next+=1; return self.next
        def begin_order_ack(self, oid): pass
        def placeOrder(self, oid, contract, order): self.placed.append((oid, order))
    class Req:
        aggregate_id='A'; transmit=True; combo_legs=(1,2)
        def validate(self): return None
    t=IbapiPaperOrderTransport(); app=App()
    monkeypatch.setattr(t,'_require',lambda:app)
    monkeypatch.setattr(t,'_build_combo_contract',lambda request:'BAG')
    monkeypatch.setattr(t,'_build_combo_order',lambda request,limit_price,transmit,order_ref:{'price':limit_price,'transmit':transmit})
    monkeypatch.setattr(t,'_combo_candidate_normalizations',lambda request:[
        {'normalized_price':10.91,'increment':0.01},
        {'normalized_price':10.90,'increment':0.05},
    ])
    acks=iter([
        {'acknowledged':False,'callback':'ERROR','status':'REJECTED','error_code':110,'error_message':'minimum price variation'},
        {'acknowledged':True,'callback':'ORDER_STATUS','status':'PRESUBMITTED','permanent_id':123},
    ])
    monkeypatch.setattr(t,'wait_for_order_acknowledgement',lambda oid:next(acks))
    oid=t.submit_combo_order(Req())
    assert oid==42
    assert [x[1]['price'] for x in app.placed]==[10.91,10.90]
    evidence=t.last_outbound_price_validation('A')['limit_price']
    assert evidence['validation']=='IBKR_ACKNOWLEDGED'
    assert evidence['candidate_attempt_count']==2


def test_timeout_does_not_advance_to_second_candidate(monkeypatch):
    from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
    class App:
        def __init__(self): self.next=50; self.placed=[]
        def reserve_order_id(self): self.next+=1; return self.next
        def begin_order_ack(self, oid): pass
        def placeOrder(self, oid, contract, order): self.placed.append((oid, order))
    class Req:
        aggregate_id='B'; transmit=True; combo_legs=(1,2)
        def validate(self): return None
    t=IbapiPaperOrderTransport();app=App()
    monkeypatch.setattr(t,'_require',lambda:app)
    monkeypatch.setattr(t,'_build_combo_contract',lambda request:'BAG')
    monkeypatch.setattr(t,'_build_combo_order',lambda request,limit_price,transmit,order_ref:{'price':limit_price,'transmit':transmit})
    monkeypatch.setattr(t,'_combo_candidate_normalizations',lambda request:[{'normalized_price':1.03,'increment':0.01},{'normalized_price':1.00,'increment':0.05}])
    monkeypatch.setattr(t,'wait_for_order_acknowledgement',lambda oid:{'acknowledged':False,'callback':'TIMEOUT','status':'AWAITING_BROKER_ACK'})
    oid=t.submit_combo_order(Req())
    assert oid==51
    assert len(app.placed)==1
    assert t.last_outbound_price_validation('B')['limit_price']['validation']=='IBKR_ACK_INCONCLUSIVE'
