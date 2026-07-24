from trading_ai.daily_scan_workstation.refresh_governance import evaluate_refresh_governance

run = evaluate_refresh_governance(requested_symbol_count=610, covered_symbol_count=609, minimum_coverage_pct=98.0, maximum_failed_symbols=10, continue_on_degraded=True)
assert run.status == "DEGRADED" and run.eligible_to_continue is True
assert round(run.coverage_pct, 2) == 99.84 and run.failed_symbol_count == 1

small = evaluate_refresh_governance(requested_symbol_count=2, covered_symbol_count=1, minimum_coverage_pct=98.0, maximum_failed_symbols=10, continue_on_degraded=True)
assert small.status == "FAILED" and small.eligible_to_continue is False

strict_count = evaluate_refresh_governance(requested_symbol_count=610, covered_symbol_count=609, minimum_coverage_pct=98.0, maximum_failed_symbols=0, continue_on_degraded=True)
assert strict_count.status == "FAILED" and strict_count.eligible_to_continue is False

blocked = evaluate_refresh_governance(requested_symbol_count=610, covered_symbol_count=609, minimum_coverage_pct=98.0, maximum_failed_symbols=10, continue_on_degraded=False)
assert blocked.status == "FAILED" and blocked.eligible_to_continue is False
print("Milestone 43 degraded refresh governance assertions passed.")
