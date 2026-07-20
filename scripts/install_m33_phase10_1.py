from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
SETTINGS=ROOT/"src/trading_ai/config/settings.py"
APP=ROOT/"src/trading_ai/ui/app.py"
INDEX=ROOT/"src/trading_ai/ui/static/index.html"
ENV_EXAMPLE=ROOT/".env.example"

def backup(path):
    target=path.with_suffix(path.suffix+".m33_phase10_1.bak")
    if path.exists() and not target.exists(): shutil.copy2(path,target)

def patch_settings():
    text=SETTINGS.read_text(encoding="utf-8")
    if "ui_local_admin_mode" in text:return
    fields="""
    ui_local_admin_mode: bool = False
    ui_bind_host: str = "127.0.0.1"
    ui_local_admin_user_id: str = "local-workstation-admin"
    ui_local_admin_display_name: str = "Local Workstation Administrator"
"""
    marker=next((x for x in ("    model_config = SettingsConfigDict(","    class Config:") if x in text),None)
    if not marker:raise RuntimeError("Unable to locate settings insertion anchor.")
    backup(SETTINGS); SETTINGS.write_text(text.replace(marker,fields+"\n"+marker,1),encoding="utf-8")

def patch_app():
    text=APP.read_text(encoding="utf-8")
    imp="from trading_ai.ui.api.local_admin_session import router as local_admin_session_router\n"
    if imp not in text:
        marker=next((x for x in (
          "from trading_ai.ui.api.ui_resilience import router as ui_resilience_router\n",
          "from trading_ai.ui.api.executive_reporting import router as executive_reporting_router\n") if x in text),None)
        if not marker:raise RuntimeError("Unable to locate UI router import anchor.")
        text=text.replace(marker,marker+imp,1)
    if "local_admin_session_router," not in text:
        marker=next((x for x in ("  ui_resilience_router,\n","  executive_reporting_router,\n") if x in text),None)
        if not marker:raise RuntimeError("Unable to locate router registration anchor.")
        text=text.replace(marker,marker+"  local_admin_session_router,\n",1)
    text=text.replace('version="33.10.0"','version="33.10.1"')
    backup(APP); APP.write_text(text,encoding="utf-8")

def patch_index():
    html=INDEX.read_text(encoding="utf-8")
    css='<link rel="stylesheet" href="/static/local_admin_mode.css">'
    js='<script src="/static/local_admin_mode.js"></script>'
    if css not in html:html=html.replace("</head>",f"  {css}\n</head>")
    if js not in html:html=html.replace("</body>",f"  {js}\n</body>")
    backup(INDEX);INDEX.write_text(html,encoding="utf-8")

def patch_env():
    if not ENV_EXAMPLE.exists():return
    text=ENV_EXAMPLE.read_text(encoding="utf-8")
    if "UI_LOCAL_ADMIN_MODE=" in text:return
    block="""
# Milestone 33 Phase 10.1
UI_LOCAL_ADMIN_MODE=false
UI_BIND_HOST=127.0.0.1
UI_LOCAL_ADMIN_USER_ID=local-workstation-admin
UI_LOCAL_ADMIN_DISPLAY_NAME=Local Workstation Administrator
"""
    backup(ENV_EXAMPLE);ENV_EXAMPLE.write_text(text.rstrip()+"\n\n"+block.strip()+"\n",encoding="utf-8")

def main():
    patch_settings();patch_app();patch_index();patch_env()
    print("Milestone 33 Phase 10.1 integration completed.")
    print("Enable UI_LOCAL_ADMIN_MODE=true and keep UI_BIND_HOST=127.0.0.1.")

if __name__=="__main__":main()
