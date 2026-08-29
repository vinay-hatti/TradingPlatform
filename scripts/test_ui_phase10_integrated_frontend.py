from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    static = root / "src/trading_ai/ui/static"

    index = (static / "index.html").read_text(encoding="utf-8")
    styles = (static / "styles.css").read_text(encoding="utf-8")
    app = (static / "app.js").read_text(encoding="utf-8")

    assert "Release Overview" in index
    assert "Identity & Sessions" in index
    assert "renderGeneric" not in app
    assert "JSON.stringify(d,null,2)" not in app
    assert "JSON.stringify(d, null, 2)" not in app

    required_renderers = [
        "renderRelease",
        "renderDashboard",
        "renderOpportunities",
        "renderSymbols",
        "renderPortfolioRisk",
        "renderExecution",
        "renderReportingAudit",
        "renderAdminRuntime",
        "renderAuthSession",
    ]
    for renderer in required_renderers:
        assert f"function {renderer}" in app, renderer

    required_apis = [
        "/api/v1/workstation-release",
        "/api/v1/dashboard",
        "/api/v1/opportunities",
        "/api/v1/symbols",
        "/api/v1/portfolio-risk",
        "/api/v1/execution",
        "/api/v1/reporting-audit",
        "/api/v1/admin-runtime",
        "/api/v1/auth-session",
    ]
    for api in required_apis:
        assert api in app, api

    assert ".table-wrap" in styles
    assert ".cards" in styles
    assert ".timeline" in styles
    assert ".grid-3" in styles

    print(
        "All corrected Milestone 31 Phase 10 integrated frontend "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
