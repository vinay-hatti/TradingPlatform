import json
from dataclasses import asdict
from pathlib import Path
def _j(v):
    if hasattr(v,"isoformat"): return v.isoformat()
    if isinstance(v,dict): return {str(k):_j(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_j(x) for x in v]
    return v
def outcome_attribution_payload(p): return _j(asdict(p))
def write_outcome_attribution_report(p,output_file):
    path=Path(output_file); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(outcome_attribution_payload(p),indent=2,sort_keys=True)+"\n"); return path
def write_thesis_validation_report(p,output_file):
    path=Path(output_file); path.parent.mkdir(parents=True,exist_ok=True); payload={"attribution_id":p.attribution_id,"case_id":p.case_id,"journal_id":p.journal_id,"symbol":p.symbol,"strategy_name":p.strategy_name,"thesis_validation":_j(p.thesis_validation),"scenario_calibration":_j(p.scenario_calibration),"forecast_accuracy":_j(p.forecast_accuracy),"decision_quality_score":p.decision_quality_score,"decision_quality_grade":p.decision_quality_grade,"research_feedback":_j(p.research_feedback)}; path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n"); return path
