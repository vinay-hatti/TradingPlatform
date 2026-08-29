import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from trading_ai.scanner.option_surface_phase_closure.contracts import (
    PhaseClosureRunProfile,
)
from trading_ai.scanner.option_surface_phase_closure.reporting import (
    render_html_report,
    write_html_report,
)


def main():
    profile = PhaseClosureRunProfile(
        as_of_date=date(2026, 7, 20),
        generated_at=datetime.now(timezone.utc),
        execution_results=(),
        required_artifacts=("a.json",),
        existing_artifacts=("a.json",),
        missing_artifacts=(),
        phase_status="COMPLETE",
        phase_reasons=(),
    )

    html = render_html_report(profile)
    assert "Milestone 35 Phase 4 Closure" in html
    assert "COMPLETE" in html
    assert "a.json" in html

    with tempfile.TemporaryDirectory() as directory:
        path = write_html_report(
            Path(directory) / "report.html",
            profile,
        )
        assert path.exists()

    print("Milestone 35 Phase 4 Step 5 reporting assertions passed.")


if __name__ == "__main__":
    main()
