import json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.models import OptionValuationPublicationModel
with SessionLocal() as s:
    p=s.execute(select(OptionValuationPublicationModel).where(OptionValuationPublicationModel.publication_name=='current_option_valuation_intelligence')).scalars().first()
    if not p: raise SystemExit('No current option valuation publication found')
    print(json.dumps({'status':p.status,'published_at':p.published_at,**dict(p.payload_json or {})},indent=2,sort_keys=True))
