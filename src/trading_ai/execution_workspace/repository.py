from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ExecutionIntentModel,ExecutionIntentAuditModel
class ExecutionIntentRepository:
 def __init__(self,s:Session):self.s=s
 def add(self,x):self.s.add(x)
 def get(self,id):return self.s.get(ExecutionIntentModel,id)
 def by_trade_plan(self,id,version):
  return self.s.scalar(select(ExecutionIntentModel).where(ExecutionIntentModel.trade_plan_id==id,ExecutionIntentModel.trade_plan_version==version).order_by(ExecutionIntentModel.execution_attempt.desc(),ExecutionIntentModel.created_at.desc()).limit(1))
 def attempts(self,id,version):
  return list(self.s.scalars(select(ExecutionIntentModel).where(ExecutionIntentModel.trade_plan_id==id,ExecutionIntentModel.trade_plan_version==version).order_by(ExecutionIntentModel.execution_attempt.desc(),ExecutionIntentModel.created_at.desc())))
 def next_attempt(self,id,version):
  latest=self.by_trade_plan(id,version);return int(getattr(latest,'execution_attempt',0) or 0)+1
 def list(self,state=None,portfolio_id=None,limit=200):
  q=select(ExecutionIntentModel).order_by(ExecutionIntentModel.updated_at.desc()).limit(limit)
  if state:q=q.where(ExecutionIntentModel.state==state)
  if portfolio_id:q=q.where(ExecutionIntentModel.portfolio_id==portfolio_id)
  return list(self.s.scalars(q))
 def audit(self,id):return list(self.s.scalars(select(ExecutionIntentAuditModel).where(ExecutionIntentAuditModel.execution_intent_id==id).order_by(ExecutionIntentAuditModel.execution_intent_version)))
