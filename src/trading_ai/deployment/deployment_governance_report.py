from dataclasses import asdict
from datetime import datetime,timezone
from html import escape
from pathlib import Path
class DeploymentGovernanceReportBuilder:
 SECTIONS=('Release Contract','Approval History','Deployment Timeline','Environment Promotion Chain','Rollback Readiness','Policy Compliance')
 def build(self,release=None,approvals=(),transitions=(),promotions=(),rollback_plan=None,compliance=None):
  def r(x):
   if x is None:return '<p>No data available.</p>'
   raw=asdict(x) if hasattr(x,'__dataclass_fields__') else x;return '<pre>'+escape(str(raw))+'</pre>'
  data=(release,[asdict(x) for x in approvals],[asdict(x) for x in transitions],[asdict(x) for x in promotions],rollback_plan,compliance or {})
  sections=''.join(f'<h2>{h}</h2>{r(v)}' for h,v in zip(self.SECTIONS,data))
  return f'<!doctype html><html><head><meta charset="utf-8"><title>Deployment Governance Report</title><style>body{{font-family:Arial;margin:32px}}h2{{border-bottom:1px solid #ccd4df}}pre{{background:#f5f7fa;padding:14px;white-space:pre-wrap}}</style></head><body><h1>Production Deployment Governance</h1><p>Generated: {datetime.now(timezone.utc).isoformat()}</p>{sections}</body></html>'
 def write(self,path,**kwargs):
  p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(self.build(**kwargs),encoding='utf-8');return p
