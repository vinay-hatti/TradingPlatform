def render_console_report(p):
    return "\n".join([
        "=" * 72,
        "Milestone 35 Phase 5 Step 1 — Cross-Asset Data Foundation",
        "=" * 72,
        f"As-of date          : {p.as_of_date}",
        f"Universe size       : {p.universe_size}",
        f"Symbols with data   : {p.symbols_read}",
        f"Features generated  : {p.symbols_generated}",
        f"READY               : {p.ready_count}",
        f"REVIEW              : {p.review_count}",
        f"EXCLUDED            : {p.excluded_count}",
        f"Output              : {p.output_path}",
    ])
