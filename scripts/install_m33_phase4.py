from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src/trading_ai/ui/app.py"; INDEX=ROOT/"src/trading_ai/ui/static/index.html"
def backup(p):
    b=p.with_suffix(p.suffix+".m33_phase4.bak")
    if not b.exists(): shutil.copy2(p,b)
def main():
    text=APP.read_text()
    imp="from trading_ai.ui.api.interactive_portfolio import router as interactive_portfolio_router\n"
    if imp not in text:
        marker="from trading_ai.ui.api.professional_order_entry import router as professional_order_entry_router\n"
        if marker not in text: marker="from trading_ai.ui.api.portfolio_risk import router as portfolio_risk_router\n"
        if marker not in text: raise RuntimeError("Could not locate portfolio/order router import")
        text=text.replace(marker,marker+imp)
    if "interactive_portfolio_router," not in text:
        marker="  professional_order_entry_router,\n" if "  professional_order_entry_router,\n" in text else "  portfolio_risk_router,\n"
        text=text.replace(marker,marker+"  interactive_portfolio_router,\n")
    text=text.replace('version="33.3.0"','version="33.4.0"')
    backup(APP);APP.write_text(text)
    html=INDEX.read_text(); js='<script src="/static/interactive_portfolio.js"></script>'
    if js not in html: html=html.replace("</body>",f"  {js}\n</body>")
    backup(INDEX);INDEX.write_text(html)
    print("Milestone 33 Phase 4 integration completed.")
if __name__=="__main__": main()
