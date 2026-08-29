from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src/trading_ai/ui/app.py"
INDEX=ROOT/"src/trading_ai/ui/static/index.html"

def backup(path):
    target=path.with_suffix(path.suffix+".m33_phase10.bak")
    if not target.exists():
        shutil.copy2(path,target)

def main():
    text=APP.read_text(encoding="utf-8")
    imp="from trading_ai.ui.api.ui_resilience import router as ui_resilience_router\n"
    if imp not in text:
        anchors=[
            "from trading_ai.ui.api.executive_reporting import router as executive_reporting_router\n",
            "from trading_ai.ui.api.security_compliance_center import router as security_compliance_center_router\n",
        ]
        marker=next((x for x in anchors if x in text),None)
        if not marker:
            raise RuntimeError("Unable to locate UI router import anchor.")
        text=text.replace(marker,marker+imp)
    if "ui_resilience_router," not in text:
        anchors=[
            "  executive_reporting_router,\n",
            "  security_compliance_center_router,\n",
        ]
        marker=next((x for x in anchors if x in text),None)
        if not marker:
            raise RuntimeError("Unable to locate router registration anchor.")
        text=text.replace(marker,marker+"  ui_resilience_router,\n")
    text=text.replace('version="33.9.0"','version="33.10.0"')
    backup(APP)
    APP.write_text(text,encoding="utf-8")

    html=INDEX.read_text(encoding="utf-8")
    css='<link rel="stylesheet" href="/static/ui_hardening.css">'
    js='<script src="/static/ui_hardening.js"></script>'
    if css not in html:
        html=html.replace("</head>",f"  {css}\n</head>")
    if js not in html:
        html=html.replace("</body>",f"  {js}\n</body>")
    if 'id="content"' in html and 'aria-live=' not in html:
        html=html.replace(
            '<div id="content"',
            '<div id="globalAriaLive" class="visually-hidden" aria-live="polite" aria-atomic="true"></div>\n<div id="content"'
        )
    backup(INDEX)
    INDEX.write_text(html,encoding="utf-8")
    print("Milestone 33 Phase 10 integration completed.")

if __name__=="__main__":
    main()
