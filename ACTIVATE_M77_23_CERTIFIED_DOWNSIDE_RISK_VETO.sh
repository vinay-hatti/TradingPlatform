#!/usr/bin/env bash
set -euo pipefail
ROOT="${PROJECT_ROOT:-/Users/vinay.hatti/TradingPlatform}"
ENV_FILE="$ROOT/.env"
[[ -d "$ROOT" ]] || { echo "ERROR: project root not found: $ROOT"; exit 2; }
[[ -f "$ROOT/data/downside_risk_veto/champion/DRVE-CHAMPION-001.json" ]] || { echo "ERROR: champion metadata missing; materialize champion first"; exit 2; }
[[ -f "$ROOT/data/downside_risk_veto/current_authority.json" ]] || { echo "ERROR: current authority missing; refresh authority first"; exit 2; }
cd "$ROOT"
uv run python scripts/verify_m77_23_certified_downside_risk_veto.py --project-root "$ROOT"
touch "$ENV_FILE"
python3 - "$ENV_FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); lines=p.read_text().splitlines() if p.exists() else []
updates={
'M77_DOWNSIDE_RISK_VETO_MODE':'ENFORCE',
'M77_DOWNSIDE_RISK_VETO_AUTHORITY':'data/downside_risk_veto/current_authority.json',
'M77_DOWNSIDE_RISK_VETO_CHAMPION_META':'data/downside_risk_veto/champion/DRVE-CHAMPION-001.json',
'M77_DOWNSIDE_RISK_VETO_MAX_AGE_SECONDS':'10800',
}
out=[];seen=set()
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        k=line.split('=',1)[0].strip()
        if k in updates:
            out.append(f'{k}={updates[k]}');seen.add(k);continue
    out.append(line)
for k,v in updates.items():
    if k not in seen:out.append(f'{k}={v}')
p.write_text('\n'.join(out).rstrip()+'\n')
PY
echo "M77.23 certified downside-risk veto ACTIVATED in ENFORCE mode."
echo "Restart the Production API / UI backend process so .env is reloaded."
