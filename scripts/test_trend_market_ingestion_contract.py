from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_TOKENS = (
    "--skip-trend-intelligence",
    "--force-trend-refresh",
    "_run_trend_intelligence_pipeline",
    "run_trend_intelligence.py",
    "run_trend_transition_intelligence.py",
    "run_trend_forecasting.py",
    "run_institutional_trend_intelligence.py",
    "run_trend_platform_integration.py",
    "trend_refreshed=trend_refreshed",
)


def _called_function_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def main() -> None:
    path = Path("scripts/run_market_ingestion.py")
    source = path.read_text(encoding="utf-8")

    for token in REQUIRED_TOKENS:
        assert token in source, f"Missing required ingestion contract token: {token}"

    tree = ast.parse(source, filename=str(path))
    main_function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "main"
        ),
        None,
    )
    assert main_function is not None, "run_market_ingestion.py must define main()"

    calls: list[tuple[str, int]] = []
    for node in ast.walk(main_function):
        if isinstance(node, ast.Call):
            name = _called_function_name(node)
            if name is not None:
                calls.append((name, node.lineno))

    trend_calls = [line for name, line in calls if name == "_run_trend_intelligence_pipeline"]
    overview_calls = [line for name, line in calls if name == "_run_market_overview"]

    assert trend_calls, "main() must call _run_trend_intelligence_pipeline()"
    assert overview_calls, "main() must call _run_market_overview()"
    assert min(trend_calls) < min(overview_calls), (
        "Trend Intelligence must run before Market Overview; "
        f"trend line={min(trend_calls)}, overview line={min(overview_calls)}"
    )

    print("All Trend Market Ingestion contract assertions passed.")


if __name__ == "__main__":
    main()
