from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import TradePlanModel,TradePlanAuditModel
class TradePlanRepository:
 def __init__(self,session:Session):self.session=session
 def add(self,item):self.session.add(item)
 def get(self,id):return self.session.get(TradePlanModel,id)
 def list(self,opportunity_id=None,limit=100):
  q=select(TradePlanModel).order_by(TradePlanModel.updated_at.desc()).limit(limit)
  if opportunity_id:q=q.where(TradePlanModel.opportunity_id==opportunity_id)
  return list(self.session.scalars(q))
 def find_source(self,opportunity_id,version,account_id,strategy):
  return self.session.scalar(select(TradePlanModel).where(TradePlanModel.opportunity_id==opportunity_id,TradePlanModel.opportunity_version==version,TradePlanModel.account_id==account_id,TradePlanModel.strategy==strategy))
 def audit(self,id):return list(self.session.scalars(select(TradePlanAuditModel).where(TradePlanAuditModel.trade_plan_id==id).order_by(TradePlanAuditModel.trade_plan_version)))
