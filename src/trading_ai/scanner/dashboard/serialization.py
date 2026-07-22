from __future__ import annotations
import json
from dataclasses import asdict,is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from .contracts import DashboardSnapshot

def _default(v:Any):
    if isinstance(v,datetime):return v.isoformat()
    if isinstance(v,Enum):return v.value
    if is_dataclass(v):return asdict(v)
    raise TypeError(type(v).__name__)
def write_json_atomic(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(payload,default=_default,indent=2,sort_keys=True),encoding='utf-8'); tmp.replace(path)
def write_dashboard_artifacts(output_dir:Path,snapshot:DashboardSnapshot):
    output_dir.mkdir(parents=True,exist_ok=True); a={k:output_dir/v for k,v in {'dashboard_state':'dashboard_state.json','scanner_session':'scanner_session.json','navigation_state':'navigation_state.json','ranking_snapshot':'ranking_snapshot.json','run':'run.json'}.items()}
    write_json_atomic(a['dashboard_state'],snapshot); write_json_atomic(a['scanner_session'],snapshot.session); write_json_atomic(a['navigation_state'],snapshot.navigation); write_json_atomic(a['ranking_snapshot'],snapshot.rankings); write_json_atomic(a['run'],{'schema_version':snapshot.schema_version,'generated_at':snapshot.generated_at,'session_id':snapshot.session.session_id,'status':snapshot.session.status,'universe_name':snapshot.session.universe_name,'progress':snapshot.progress,'ranking_count':len(snapshot.rankings),'event_count':len(snapshot.events)})
    return a
