from __future__ import annotations
import html
from pathlib import Path
from .serialization import read_json

class PositionManagementReportingService:
    def render(self, assessment_file: str, instruction_file: str, output_file: str) -> str:
        assessments = read_json(assessment_file, {}).get("assessments", [])
        instructions = read_json(instruction_file, {}).get("instructions", [])
        rows = "".join(f"<tr><td>{html.escape(str(x.get('symbol','')))}</td><td>{x.get('decision')}</td><td>{x.get('urgency')}</td><td>{x.get('return_pct',0):.2%}</td><td>{html.escape(', '.join(x.get('reasons',[])))}</td></tr>" for x in assessments)
        body = f"""<!doctype html><html><head><meta charset='utf-8'><title>Milestone 39 Position Monitoring</title><style>body{{font-family:Arial;margin:2rem}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:.5rem;text-align:left}}th{{background:#eee}}</style></head><body><h1>Milestone 39 — Position Monitoring and Exit Intelligence</h1><p>Positions assessed: {len(assessments)} | Exit instructions: {len(instructions)}</p><table><thead><tr><th>Symbol</th><th>Decision</th><th>Urgency</th><th>Return</th><th>Reasons</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
        p=Path(output_file); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body,encoding='utf-8'); return str(p)
