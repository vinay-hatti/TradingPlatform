#!/usr/bin/env bash
set -euo pipefail
ROOT="${PROJECT_ROOT:-/Users/vinay.hatti/TradingPlatform}"
ENV_FILE="$ROOT/.env"
touch "$ENV_FILE"
python3 - "$ENV_FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);lines=p.read_text().splitlines() if p.exists() else [];out=[];found=False
for line in lines:
    if line.startswith('M77_DOWNSIDE_RISK_VETO_MODE='):
        out.append('M77_DOWNSIDE_RISK_VETO_MODE=OFF');found=True
    else:out.append(line)
if not found:out.append('M77_DOWNSIDE_RISK_VETO_MODE=OFF')
p.write_text('\n'.join(out).rstrip()+'\n')
PY
echo "M77.23 downside-risk veto set to OFF. Restart Production API / backend to reload .env."
