
SCENARIOS=['single_leg_stop','single_leg_take_profit','vertical_spread_stop','vertical_spread_target','gap_through_stop','target1_scale_out','target2_after_partial_exit','stop_after_partial_profit','multiple_triggers_same_cycle','partial_broker_fill','unfilled_exit_order','cancel_reprice_replace','polygon_unavailable','ibkr_unavailable','manager_restart_open_position','position_discovered_m63_only','stale_quote_protection','quantity_mismatch','manual_broker_exit','emergency_kill_switch','final_flat_reconciliation','m72_outcome_generation']
print('M73 controlled-paper acceptance')
for s in SCENARIOS:print(f'PENDING  {s}')
print(f'PASS 0/{len(SCENARIOS)} | PENDING {len(SCENARIOS)}/{len(SCENARIOS)} | M73 COMPLETE: NO')
