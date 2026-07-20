from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src/trading_ai/ui/app.py"
INDEX=ROOT/"src/trading_ai/ui/static/index.html"
def backup(path):
    target=path.with_suffix(path.suffix+".m33_phase5.bak")
    if not target.exists(): shutil.copy2(path,target)
def main():
    text=APP.read_text(encoding="utf-8")
    imp="from trading_ai.ui.api.research_workbench import router as research_workbench_router\n"
    if imp not in text:
        anchors=["from trading_ai.ui.api.interactive_portfolio import router as interactive_portfolio_router\n","from trading_ai.ui.api.reporting_audit import router as reporting_audit_router\n"]
        marker=next((x for x in anchors if x in text),None)
        if not marker: raise RuntimeError("Unable to locate UI router import anchor")
        text=text.replace(marker,marker+imp)
    if "research_workbench_router," not in text:
        anchors=["  interactive_portfolio_router,\n","  reporting_audit_router,\n"]
        marker=next((x for x in anchors if x in text),None)
        if not marker: raise RuntimeError("Unable to locate router registration anchor")
        text=text.replace(marker,marker+"  research_workbench_router,\n")
    text=text.replace('version="33.4.0"','version="33.5.0"')
    backup(APP); APP.write_text(text,encoding="utf-8")
    html=INDEX.read_text(encoding="utf-8")
    js='<script src="/static/research_workbench.js"></script>'
    if js not in html: html=html.replace("</body>",f"  {js}\n</body>")
    backup(INDEX); INDEX.write_text(html,encoding="utf-8")
    print("Milestone 33 Phase 5 integration completed.")
if __name__=="__main__": main()
