#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
SRC_DIR="$TARGET/ui/workstation/src"
TEST_DIR="$TARGET/ui/workstation/tests"
[[ -d "$SRC_DIR" ]] || { echo "Missing workstation source: $SRC_DIR" >&2; exit 1; }
BACKUP="$TARGET/.ui_milestone7_backup_$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP" "$TEST_DIR"
for file in App.tsx api.ts types.ts PortfolioIntelligenceRefinedPage.tsx portfolio-intelligence-refined.css; do
  [[ -f "$SRC_DIR/$file" ]] && cp "$SRC_DIR/$file" "$BACKUP/$file"
done
cp "$(dirname "$0")/files/ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx" "$SRC_DIR/"
cp "$(dirname "$0")/files/ui/workstation/src/portfolio-intelligence-refined.css" "$SRC_DIR/"
cp "$(dirname "$0")/files/ui/workstation/tests/ui-milestone7-portfolio-intelligence.test.mjs" "$TEST_DIR/"
python3 - "$SRC_DIR" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1])

types=src/'types.ts'
t=types.read_text()
block="""

export type PositionHealthDriver={category:string;score:number;direction:string;contribution:number;reason:string};
export type ManagedPosition={position_id:string;portfolio_id:string;trade_plan_id:string;opportunity_id:string;intelligence_id:string|null;execution_id:string|null;symbol:string;strategy:string;direction:string;state:string;version:number;opened_at:string;closed_at:string|null;entry_value:number;realized_pnl:number;mark:{mark_price:number;quantity:number;market_value:number;unrealized_pnl:number;unrealized_return_pct:number;delta:number;gamma:number;theta:number;vega:number;days_to_expiry:number|null};health:{score:number;direction:string;confidence:number;drivers:PositionHealthDriver[];alerts:string[]};decision:{action:string;confidence:number;priority:string;reason:string;expected_benefit:string;risk_impact:string;alternatives:string[]};metadata:Record<string,any>};
export type PortfolioIntelligenceSnapshot={snapshot_id?:string;portfolio_id:string;snapshot_timestamp:string;net_liquidation:number;cash:number;buying_power:number;market_value:number;unrealized_pnl:number;realized_pnl:number;open_risk:number;health_score:number;position_count:number;greeks:Record<string,number>;sector_exposure:Record<string,number>;strategy_exposure:Record<string,number>;concentration:Record<string,number>};
"""
if 'export type ManagedPosition=' not in t:
    types.write_text(t.rstrip()+block+'\n')

api=src/'api.ts'
a=api.read_text()
if 'ManagedPosition' not in a.split('\n',1)[0]:
    a=a.replace("TradePlan } from './types';", "TradePlan, ManagedPosition, PortfolioIntelligenceSnapshot } from './types';")
if 'const PORTFOLIO_INTELLIGENCE_ROOT=' not in a:
    marker="const OPPORTUNITY_ROOT="
    idx=a.find(marker)
    if idx >= 0:
        end=a.find('\n',idx)
        a=a[:end+1]+"const PORTFOLIO_INTELLIGENCE_ROOT=(import.meta.env.VITE_PORTFOLIO_INTELLIGENCE_API_ROOT||'/api/v1/portfolio-intelligence').replace(/\/$/,'');\n"+a[end+1:]
    else:
        a="const PORTFOLIO_INTELLIGENCE_ROOT=(import.meta.env.VITE_PORTFOLIO_INTELLIGENCE_API_ROOT||'/api/v1/portfolio-intelligence').replace(/\/$/,'');\n"+a
if 'export const portfolioIntelligenceApi=' not in a:
    a += "\n\nexport const portfolioIntelligenceApi={positions:(portfolioId='PAPER-PRIMARY')=>request<ManagedPosition[]>(`${PORTFOLIO_INTELLIGENCE_ROOT}/positions?portfolio_id=${encodeURIComponent(portfolioId)}`,{headers:headers()}),snapshot:(portfolioId:string)=>request<PortfolioIntelligenceSnapshot|null>(`${PORTFOLIO_INTELLIGENCE_ROOT}/portfolios/${encodeURIComponent(portfolioId)}/snapshot`,{headers:headers()}),generateSnapshot:(portfolioId:string,cash:number,buyingPower:number)=>request<PortfolioIntelligenceSnapshot>(`${PORTFOLIO_INTELLIGENCE_ROOT}/portfolios/${encodeURIComponent(portfolioId)}/snapshots`,{method:'POST',headers:headers(true),body:JSON.stringify({cash,buying_power:buyingPower})}),action:(id:string,expectedVersion:number,action:string,reason:string,realizedPnl=0)=>request<ManagedPosition>(`${PORTFOLIO_INTELLIGENCE_ROOT}/positions/${encodeURIComponent(id)}/actions`,{method:'POST',headers:headers(true),body:JSON.stringify({expected_version:expectedVersion,action,reason,realized_pnl:realizedPnl})})};\n"
api.write_text(a)

app=src/'App.tsx'
s=app.read_text()
imp="import { PortfolioIntelligenceRefinedPage } from './PortfolioIntelligenceRefinedPage';"
if imp not in s:
    lines=s.splitlines()
    last_import=max(i for i,line in enumerate(lines) if line.startswith('import '))
    lines.insert(last_import+1,imp)
    s='\n'.join(lines)+'\n'
# Replace the page mapping only, preserving all shell logic.
import re
s=re.sub(r"(^\s*portfolio:\s*)[^,]+,",r"\1PortfolioIntelligenceRefinedPage,",s,flags=re.M)
app.write_text(s)
PY
STATUS="$TARGET/PROJECT_STATUS.md"
if [[ -f "$STATUS" ]] && ! grep -q "UI Milestone 7 — Portfolio Intelligence Command Center" "$STATUS"; then
cat >> "$STATUS" <<'STATUS_EOF'

## UI Milestone 7 — Portfolio Intelligence Command Center
- Status: COMPLETE
- Refined managed-position queue, portfolio health, aggregate Greeks, exposure, alerts, explainable decisions, and governed lifecycle actions.
- Existing Milestone 57 APIs and IBKR paper-order governance remain authoritative.
STATUS_EOF
fi
printf '%s\n' "$BACKUP" > "$TARGET/.ui_milestone7_last_backup"
echo "UI Milestone 7 applied. Backup: $BACKUP"
echo "Run npm test, npm run typecheck, and npm run build in ui/workstation."
