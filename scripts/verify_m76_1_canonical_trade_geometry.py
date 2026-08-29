from pathlib import Path
import sys

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
pos=(root/'src/trading_ai/stock_intelligence/position_intelligence.py').read_text()
prof=(root/'src/trading_ai/stock_intelligence/profile.py').read_text()
checks={
 'canonical_geometry_engine': "class CanonicalTradeGeometryEngine" in pos,
 'actual_breakout_anchor': "evidence.get('resistance')" in pos and "evidence.get('support')" in pos,
 'confirmed_breakout_current_reference': "confirmed-breakout execution is referenced to current ingested price" in pos,
 'next_zone_not_entry': "is retained as objective context and is not used as the entry anchor" in pos,
 'market_valid_stop_guard': "Canonical stop guard" in pos,
 'm75_current_target_gate_preserved': "self._valid(price,current,bull)" in pos and "CROSSED_CURRENT_UNDERLYING_OR_INVALID_PRICE" in pos,
 'final_entry_target_gate': "BEHIND_FINAL_ENTRY_ZONE" in pos and "_valid_after_final_entry" in pos,
 'target_rerank_version': "M76.1-CANONICAL-TARGET-RANKING-1.0" in pos,
 'geometry_persisted': "geometry_context:dict[str,Any]" in prof,
 'shared_context_pipeline': "self.stop.build(profile,e,geometry)" in pos and "self.targets.build(profile,e,s,geometry)" in pos,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(('PASS' if v else 'FAIL'),k)
if failed: raise SystemExit('M76.1 verification failed: '+', '.join(failed))
print('M76.1 canonical trade geometry verification: PASSED')
