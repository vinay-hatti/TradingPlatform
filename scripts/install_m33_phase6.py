from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src/trading_ai/ui/app.py"
INDEX=ROOT/"src/trading_ai/ui/static/index.html"

def backup(path):
    target=path.with_suffix(path.suffix+".m33_phase6.bak")
    if not target.exists():
        shutil.copy2(path,target)

def main():
    text=APP.read_text(encoding="utf-8")
    imp="from trading_ai.ui.api.strategy_studio import router as strategy_studio_router\n"
    if imp not in text:
        anchors=[
            "from trading_ai.ui.api.research_workbench import router as research_workbench_router\n",
            "from trading_ai.ui.api.admin_runtime import router as admin_runtime_router\n",
        ]
        marker=next((x for x in anchors if x in text),None)
        if not marker:
            raise RuntimeError("Unable to locate UI router import anchor")
        text=text.replace(marker,marker+imp)
    if "strategy_studio_router," not in text:
        anchors=["  research_workbench_router,\n","  admin_runtime_router,\n"]
        marker=next((x for x in anchors if x in text),None)
        if not marker:
            raise RuntimeError("Unable to locate router registration anchor")
        text=text.replace(marker,marker+"  strategy_studio_router,\n")
    text=text.replace('version="33.5.0"','version="33.6.0"')
    backup(APP); APP.write_text(text,encoding="utf-8")

    html=INDEX.read_text(encoding="utf-8")
    js='<script src="/static/strategy_studio.js"></script>'
    if js not in html:
        html=html.replace("</body>",f"  {js}\n</body>")
    backup(INDEX); INDEX.write_text(html,encoding="utf-8")
    print("Milestone 33 Phase 6 integration completed.")

if __name__=="__main__":
    main()
