from fastapi import APIRouter,Request,HTTPException
router=APIRouter(prefix='/api/v1/market-intelligence',tags=['market-intelligence'])
def svc(r:Request):return r.app.state.m46_market_intelligence_service
@router.get('/latest')
def latest(request:Request):
    x=svc(request).latest()
    if not x:raise HTTPException(404,'No Market Intelligence snapshot available.')
    return {'data':x,'source':'market_intelligence_snapshot'}
@router.post('/refresh')
def refresh(request:Request):return {'data':svc(request).build(persist=True).to_dict(),'source':'market_intelligence_snapshot'}
@router.get('/scanner-context')
def scanner_context(request:Request):return {'data':svc(request).scanner_context(),'source':'market_intelligence_snapshot'}
@router.get('/correlation')
def correlation(request:Request):return {'data':(svc(request).latest() or {}).get('correlation',{}),'source':'correlation_snapshot'}
@router.get('/sectors')
def sectors(request:Request):return {'data':(svc(request).latest() or {}).get('sector_breadth',[]),'source':'sector_breadth_snapshot'}
@router.get('/dealer-migration')
def dealer(request:Request):return {'data':(svc(request).latest() or {}).get('dealer_ensemble',[]),'source':'dealer_position_change_snapshot'}
@router.get('/risk')
def risk(request:Request):return {'data':(svc(request).latest() or {}).get('risk',{}),'source':'market_risk_snapshot'}
@router.get('/opportunities')
def opportunities(request:Request):return {'data':(svc(request).latest() or {}).get('opportunities',[]),'source':'market_opportunity_snapshot'}
