from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src/trading_ai/ui/app.py"
INDEX=ROOT/"src/trading_ai/ui/static/index.html"
def backup(p):
    b=p.with_suffix(p.suffix+".m33_phase3.bak")
    if not b.exists(): shutil.copy2(p,b)
def main():
    text=APP.read_text()
    imp="from trading_ai.ui.api.professional_order_entry import router as professional_order_entry_router\n"
    if imp not in text:
        marker="from trading_ai.ui.api.option_chain import router as option_chain_router\n"
        if marker not in text: marker="from trading_ai.ui.api.paper_commands import router as paper_commands_router\n"
        text=text.replace(marker,marker+imp)
    if "professional_order_entry_router," not in text:
        marker="  option_chain_router,\n" if "  option_chain_router,\n" in text else "  paper_commands_router,\n"
        text=text.replace(marker,marker+"  professional_order_entry_router,\n")
    text=text.replace('version="33.2.0"','version="33.3.0"')
    backup(APP);APP.write_text(text)
    html=INDEX.read_text()
    js='<script src="/static/professional_order_entry.js"></script>'
    if js not in html: html=html.replace("</body>",f"  {js}\n</body>")
    backup(INDEX);INDEX.write_text(html)
    print("Milestone 33 Phase 3 integration completed.")
if __name__=="__main__": main()
