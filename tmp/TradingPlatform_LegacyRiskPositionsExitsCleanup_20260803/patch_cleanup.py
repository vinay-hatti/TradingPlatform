from __future__ import annotations
from pathlib import Path
import shutil, sys, datetime


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0:
        if new in text:
            return text
        raise RuntimeError(f"Could not find expected {label} block")
    if count != 1:
        raise RuntimeError(f"Expected one {label} block, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    backup = root / 'backups' / f'legacy_risk_positions_exits_cleanup_{stamp}'
    files = [
        root/'ui/workstation/src/App.tsx',
        root/'ui/workstation/src/WorkspaceChrome.tsx',
        root/'ui/workstation/src/pages.tsx',
        root/'src/trading_ai/production_api/router.py',
    ]
    for f in files:
        if not f.exists(): raise FileNotFoundError(f)
        dest = backup / f.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)

    app = files[0].read_text()
    app = app.replace(
        "import { CommandCenter, DailyScannerPage, Exits, MarketOverviewPage, OptionScannerPage, OpportunityWorkspacePage, Overview, Positions, Risk } from './pages';",
        "import { CommandCenter, DailyScannerPage, MarketOverviewPage, OptionScannerPage, OpportunityWorkspacePage, Overview } from './pages';",
    )
    app = app.replace(
        "  risk: Risk, 'execution-workspace': ExecutionWorkspacePage, execution: ExecutionWorkspacePage, positions: Positions, exits: Exits, command: CommandCenter,",
        "  'execution-workspace': ExecutionWorkspacePage, execution: ExecutionWorkspacePage, risk: PortfolioIntelligenceRefinedPage, positions: PortfolioIntelligenceRefinedPage, exits: PortfolioIntelligenceRefinedPage, command: CommandCenter,",
    )
    old_route = """  if (value === 'execution') {\n    if (location.hash !== '#/execution-workspace') history.replaceState(null, '', '#/execution-workspace');\n    return 'execution-workspace';\n  }\n  return value in pages ? value : 'overview';"""
    new_route = """  if (value === 'execution') {\n    if (location.hash !== '#/execution-workspace') history.replaceState(null, '', '#/execution-workspace');\n    return 'execution-workspace';\n  }\n  if (value === 'risk' || value === 'positions' || value === 'exits') {\n    if (location.hash !== '#/portfolio') history.replaceState(null, '', '#/portfolio');\n    return 'portfolio';\n  }\n  return value in pages ? value : 'overview';"""
    app = replace_once(app, old_route, new_route, 'route redirect')
    files[0].write_text(app)

    chrome = files[1].read_text()
    chrome = replace_once(
        chrome,
        "  { label: 'Portfolio', items: ['portfolio', 'performance-learning', 'risk', 'positions', 'exits'] },",
        "  { label: 'Portfolio', items: ['portfolio', 'performance-learning'] },",
        'portfolio navigation group',
    )
    files[1].write_text(chrome)

    pages = files[2].read_text()
    for line in [
        "  ['risk', 'Risk', ShieldCheck],\n",
        "  ['positions', 'Positions', ScanLine],\n",
        "  ['exits', 'Exits', LogOut],\n",
    ]:
        pages = pages.replace(line, '')
    files[2].write_text(pages)

    router = files[3].read_text()
    old_risk = '''@router.get("/risk", response_model=ApiEnvelope)\ndef risk(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):\n    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m37/execution_risk_control.json"))\n'''
    new_risk = '''@router.get("/risk", response_model=ApiEnvelope)\ndef risk(request: Request, _: str = Depends(require_access)):\n    """Compatibility view backed by canonical Portfolio Intelligence data."""\n    from trading_ai.database.session import SessionLocal\n    from trading_ai.portfolio_intelligence.repository import PortfolioRepository\n    from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService\n\n    with SessionLocal() as session:\n        repo = PortfolioRepository(session)\n        positions = repo.list(portfolio_id="PAPER-PRIMARY")\n        active = [item for item in positions if item.state not in ("CLOSED", "CANCELLED")]\n        snapshot = repo.latest_snapshot("PAPER-PRIMARY")\n        blocking = [item.position_id for item in active if float((item.health_json or {}).get("score", 100)) < 40]\n        recommendations = []\n        for item in active:\n            decision = item.decision_json or {}\n            action = str(decision.get("action", "HOLD"))\n            if action != "HOLD":\n                recommendations.append(f"{item.symbol}: {action} — {decision.get('reason', 'Review position intelligence')}")\n        payload = {\n            "portfolio_id": "PAPER-PRIMARY",\n            "risk_status": "CRITICAL" if blocking else "REVIEW" if recommendations else "READY",\n            "status": "CRITICAL" if blocking else "REVIEW" if recommendations else "READY",\n            "trading_control": "BLOCK_NEW_RISK" if blocking else "ALLOW_GOVERNED_RISK",\n            "allow_new_risk": not blocking,\n            "blocking_breach_ids": blocking,\n            "recommendations": recommendations or ["No active governed risk intervention."],\n            "active_position_count": len(active),\n            "positions": [PortfolioIntelligenceService.dto(item) for item in active],\n            "portfolio_snapshot": ({"snapshot_id": snapshot.snapshot_id, **snapshot.payload_json} if snapshot else None),\n        }\n        return envelope(request, payload, source="canonical_portfolio_intelligence", compatibility_alias=True)\n'''
    router = replace_once(router, old_risk, new_risk, 'risk endpoint')

    old_positions = '''@router.get("/positions", response_model=ApiEnvelope)\ndef positions(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):\n    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m39/position_assessments.json"))\n'''
    new_positions = '''@router.get("/positions", response_model=ApiEnvelope)\ndef positions(request: Request, _: str = Depends(require_access)):\n    """Compatibility view backed by canonical managed positions."""\n    from trading_ai.database.session import SessionLocal\n    from trading_ai.portfolio_intelligence.repository import PortfolioRepository\n    from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService\n\n    with SessionLocal() as session:\n        items = PortfolioRepository(session).list(portfolio_id="PAPER-PRIMARY")\n        data = [PortfolioIntelligenceService.dto(item) for item in items]\n        return envelope(request, data, count=len(data), source="canonical_managed_positions", compatibility_alias=True)\n'''
    router = replace_once(router, old_positions, new_positions, 'positions endpoint')

    old_exits = '''@router.get("/exit-instructions", response_model=ApiEnvelope)\ndef exits(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):\n    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m39/exit_instructions.json"))\n'''
    new_exits = '''@router.get("/exit-instructions", response_model=ApiEnvelope)\ndef exits(request: Request, _: str = Depends(require_access)):\n    """Compatibility view derived from canonical Portfolio Decision Intelligence."""\n    from trading_ai.database.session import SessionLocal\n    from trading_ai.portfolio_intelligence.repository import PortfolioRepository\n\n    with SessionLocal() as session:\n        items = PortfolioRepository(session).list(portfolio_id="PAPER-PRIMARY")\n        instructions = []\n        for item in items:\n            if item.state in ("CLOSED", "CANCELLED"):\n                continue\n            decision = item.decision_json or {}\n            action = str(decision.get("action", "HOLD"))\n            instructions.append({\n                "position_id": item.position_id,\n                "symbol": item.symbol,\n                "strategy": item.strategy,\n                "action": action,\n                "quantity": None,\n                "order_type": "GOVERNED_POSITION_ACTION",\n                "status": item.state,\n                "urgency": decision.get("priority", "LOW"),\n                "confidence": decision.get("confidence"),\n                "reason": decision.get("reason"),\n                "expected_benefit": decision.get("expected_benefit"),\n                "risk_impact": decision.get("risk_impact"),\n                "position_version": item.version,\n            })\n        return envelope(request, instructions, count=len(instructions), source="canonical_position_decisions", compatibility_alias=True)\n'''
    router = replace_once(router, old_exits, new_exits, 'exit endpoint')
    files[3].write_text(router)

    marker = root/'LEGACY_RISK_POSITIONS_EXITS_CLEANUP_APPLIED.txt'
    marker.write_text(f'Applied at {stamp}\nBackup: {backup}\n')
    print(f'Legacy Risk/Positions/Exits cleanup applied. Backup: {backup}')

if __name__ == '__main__': main()
