from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import socket
import sys
from typing import Callable

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from trading_ai.ui.command_runner import CommandResult, CommandRunner
from trading_ai.ui.report_browser import discover_reports, read_text_file


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = repository_root()
RUNNER = CommandRunner(
    REPO_ROOT,
    python_executable=sys.executable,
)


def initialize_state() -> None:
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_output", "")
    st.session_state.setdefault("confirmation", {})


def shell_safe_symbols(value: str) -> str:
    symbols = []
    for raw in value.split(","):
        symbol = raw.strip().upper()
        if not symbol:
            continue
        normalized = symbol.replace("_", ".")
        allowed = all(
            character.isalnum() or character in {".", "-"}
            for character in normalized
        )
        if not allowed:
            raise ValueError(
                f"Unsupported symbol characters in '{symbol}'"
            )
        symbols.append(normalized)

    if not symbols:
        raise ValueError("At least one symbol is required")
    return ",".join(dict.fromkeys(symbols))


def render_result(result: CommandResult | None) -> None:
    if result is None:
        return

    if result.succeeded:
        st.success(
            f"{result.name} completed in "
            f"{result.duration_seconds:.1f}s."
        )
    else:
        st.error(
            f"{result.name} failed with exit code "
            f"{result.return_code}."
        )

    st.code(
        RUNNER.display_command(result.command),
        language="bash",
    )
    st.text_area(
        "Command output",
        result.output,
        height=420,
        key=f"result-{result.started_at}",
    )


def run_with_streaming(
    name: str,
    command: list[str],
    *,
    timeout_seconds: float | None = None,
) -> None:
    st.session_state["last_output"] = ""
    output = st.empty()
    status = st.status(
        f"Running {name}…",
        expanded=True,
    )

    def update(text: str) -> None:
        st.session_state["last_output"] = text
        output.code(text[-30_000:], language="text")

    result = RUNNER.run(
        name,
        command,
        output_callback=update,
        timeout_seconds=timeout_seconds,
        environment=os.environ.copy(),
    )
    st.session_state["last_result"] = result

    if result.succeeded:
        status.update(
            label=f"{name} completed",
            state="complete",
            expanded=False,
        )
    else:
        status.update(
            label=f"{name} failed",
            state="error",
            expanded=True,
        )

    render_result(result)


def date_value(value: date) -> str:
    return value.isoformat()


def render_overview() -> None:
    st.subheader("Local runtime overview")

    columns = st.columns(4)
    columns[0].metric(
        "Python",
        f"{sys.version_info.major}.{sys.version_info.minor}",
    )
    columns[1].metric(
        "Repository",
        REPO_ROOT.name,
    )
    columns[2].metric(
        "Reports",
        len(discover_reports(REPO_ROOT)),
    )
    columns[3].metric(
        "PostgreSQL",
        "Reachable" if port_open("localhost", 5432) else "Unavailable",
    )

    st.code(str(REPO_ROOT), language="text")

    checks = {
        ".env": (REPO_ROOT / ".env").exists(),
        "pyproject.toml": (REPO_ROOT / "pyproject.toml").exists(),
        "Alembic": (REPO_ROOT / "alembic.ini").exists(),
        "Trading package": (REPO_ROOT / "src/trading_ai").exists(),
        "Market cache": (REPO_ROOT / ".cache/market").exists(),
    }
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Check": name,
                    "Status": "Ready" if ready else "Missing",
                }
                for name, ready in checks.items()
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Common actions")
    left, middle, right = st.columns(3)

    if left.button(
        "Run local doctor",
        use_container_width=True,
    ):
        run_with_streaming(
            "Local doctor",
            RUNNER.module_command("local-doctor"),
            timeout_seconds=120,
        )

    if middle.button(
        "Apply migrations",
        use_container_width=True,
    ):
        run_with_streaming(
            "Alembic upgrade",
            [
                sys.executable,
                "-m",
                "alembic",
                "upgrade",
                "head",
            ],
            timeout_seconds=300,
        )

    if right.button(
        "Show CLI help",
        use_container_width=True,
    ):
        run_with_streaming(
            "CLI help",
            RUNNER.module_command("--help"),
            timeout_seconds=60,
        )


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection(
            (host, port),
            timeout=0.5,
        ):
            return True
    except OSError:
        return False


def render_ingestion() -> None:
    st.subheader("Market-data ingestion")
    st.caption(
        "Downloads historical daily data through the existing "
        "`ingest-market` command."
    )

    symbols = st.text_input(
        "Symbols",
        value="AAPL,MSFT,NVDA",
        key="ingestion-symbols",
    )
    lookback = st.number_input(
        "Lookback days",
        min_value=30,
        max_value=3650,
        value=365,
        step=30,
    )

    first, second, third = st.columns(3)
    workers = first.number_input(
        "Workers",
        min_value=1,
        max_value=10,
        value=1,
    )
    interval = second.number_input(
        "Request interval (seconds)",
        min_value=0.0,
        max_value=120.0,
        value=20.0,
        step=5.0,
    )
    retries = third.number_input(
        "Maximum retries",
        min_value=0,
        max_value=20,
        value=8,
    )

    first, second = st.columns(2)
    continue_on_error = first.checkbox(
        "Continue when a symbol fails",
        value=True,
    )
    force_refresh = second.checkbox(
        "Force refresh cached data",
        value=False,
    )

    if st.button(
        "Start ingestion",
        type="primary",
        use_container_width=True,
    ):
        try:
            normalized = shell_safe_symbols(symbols)
        except ValueError as exc:
            st.error(str(exc))
            return

        command = RUNNER.module_command(
            "ingest-market",
            "--symbols",
            normalized,
            "--lookback-days",
            str(int(lookback)),
            "--max-workers",
            str(int(workers)),
            "--request-interval",
            str(float(interval)),
            "--max-retries",
            str(int(retries)),
            "--initial-backoff",
            "60",
            "--max-backoff",
            "600",
        )
        if continue_on_error:
            command.append("--continue-on-error")
        if force_refresh:
            command.append("--force-refresh")

        run_with_streaming(
            "Market ingestion",
            command,
            timeout_seconds=14_400,
        )


def render_features() -> None:
    st.subheader("Feature generation")

    first, second, third = st.columns(3)
    symbol = first.text_input(
        "Symbol",
        value="AAPL",
        key="feature-symbol",
    )
    period = second.selectbox(
        "Period",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        index=2,
    )
    interval = third.selectbox(
        "Interval",
        ["1d", "1h", "30m", "15m"],
        index=0,
    )

    save_output = st.checkbox(
        "Write CSV output",
        value=True,
    )

    if st.button(
        "Build features",
        type="primary",
        use_container_width=True,
    ):
        normalized = shell_safe_symbols(symbol)
        if "," in normalized:
            st.error("Feature generation accepts one symbol.")
            return

        command = RUNNER.module_command(
            "build-features",
            "--symbol",
            normalized,
            "--period",
            period,
            "--interval",
            interval,
        )
        if save_output:
            command.extend(
                [
                    "--output",
                    (
                        "reports/features/"
                        f"{normalized}_{period}_{interval}.csv"
                    ),
                ]
            )

        run_with_streaming(
            "Feature generation",
            command,
            timeout_seconds=900,
        )


def render_scanner() -> None:
    st.subheader("Trade scanner")

    universe_mode = st.radio(
        "Universe",
        ["Custom symbols", "S&P 500 top 100"],
        horizontal=True,
    )

    symbols = st.text_area(
        "Custom symbols",
        value=(
            "AMZN,GOOGL,META,AVGO,TSLA,LLY,JPM,"
            "BRK.B,SPY,QQQ,IWM,GLD"
        ),
        disabled=universe_mode != "Custom symbols",
    )

    today = date.today()
    first, second = st.columns(2)
    start = first.date_input(
        "History start",
        value=today - timedelta(days=365),
    )
    end = second.date_input(
        "History end",
        value=today,
    )

    first, second, third = st.columns(3)
    minimum_score = first.slider(
        "Minimum score",
        min_value=0.0,
        max_value=100.0,
        value=60.0,
        step=1.0,
    )
    top = second.number_input(
        "Maximum candidates",
        min_value=1,
        max_value=100,
        value=25,
    )
    pricing_dte = third.number_input(
        "Pricing DTE",
        min_value=1,
        max_value=365,
        value=30,
    )

    allow_network = st.checkbox(
        "Allow Polygon fallback during scan",
        value=False,
        help=(
            "Keep this disabled when using cache-only scans to avoid "
            "provider rate limits."
        ),
    )

    if st.button(
        "Run trade scan",
        type="primary",
        use_container_width=True,
    ):
        command = RUNNER.module_command(
            "generate-signals",
            "--start",
            date_value(start),
            "--end",
            date_value(end),
            "--min-score",
            str(float(minimum_score)),
            "--top",
            str(int(top)),
            "--pricing-dte",
            str(int(pricing_dte)),
        )

        if universe_mode == "Custom symbols":
            try:
                normalized = shell_safe_symbols(symbols)
            except ValueError as exc:
                st.error(str(exc))
                return
            command.extend(["--symbols", normalized])
        else:
            command.extend(
                ["--universe", "sp500-top100"]
            )

        if allow_network:
            command.append("--allow-network")

        run_with_streaming(
            "Trade scan",
            command,
            timeout_seconds=7_200,
        )


def render_paper_trading() -> None:
    st.subheader("Paper trading")

    st.warning(
        "These controls change the local paper-trading state. "
        "They do not submit live broker orders."
    )

    first, second, third = st.columns(3)

    if first.button(
        "Paper status",
        use_container_width=True,
    ):
        run_with_streaming(
            "Paper status",
            RUNNER.module_command("paper", "status"),
            timeout_seconds=120,
        )

    if second.button(
        "Mark positions",
        use_container_width=True,
    ):
        run_with_streaming(
            "Mark paper positions",
            RUNNER.module_command("paper", "mark"),
            timeout_seconds=1_800,
        )

    if third.button(
        "Create paper trades",
        type="primary",
        use_container_width=True,
    ):
        run_with_streaming(
            "Create paper trades",
            RUNNER.module_command("paper", "run"),
            timeout_seconds=1_800,
        )

    st.divider()
    confirm = st.checkbox(
        "I understand reset deletes local paper state",
        value=False,
    )
    if st.button(
        "Reset paper state",
        disabled=not confirm,
        use_container_width=True,
    ):
        run_with_streaming(
            "Reset paper state",
            RUNNER.module_command("paper", "reset"),
            timeout_seconds=120,
        )


def render_tests() -> None:
    st.subheader("Validation and tests")

    choices = {
        "Local runtime CLI": "scripts/test_local_runtime_cli.py",
        "Market ingestion contract": "scripts/test_market_ingestion_contract.py",
        "Indicator engine contract": "scripts/test_indicator_engine_contract.py",
        "Black-Scholes compatibility": "scripts/test_black_scholes_pricing_compatibility.py",
        "S&P 500 top-100 universe": "scripts/test_sp500_top100_universe.py",
        "Cache range validation": "scripts/test_market_cache_range_validation.py",
        "Target-delta strike selection": "scripts/test_target_delta_strike_selection.py",
        "Final project closure": "scripts/test_final_project_closure.py",
    }

    selected = st.multiselect(
        "Tests",
        list(choices),
        default=[
            name
            for name, script in choices.items()
            if (REPO_ROOT / script).exists()
        ][:4],
    )

    missing = [
        name
        for name in selected
        if not (REPO_ROOT / choices[name]).exists()
    ]
    if missing:
        st.info(
            "Unavailable in the current checkout: "
            + ", ".join(missing)
        )

    if st.button(
        "Run selected tests",
        type="primary",
        use_container_width=True,
    ):
        existing = [
            (name, choices[name])
            for name in selected
            if (REPO_ROOT / choices[name]).exists()
        ]

        if not existing:
            st.error("No available tests were selected.")
            return

        combined = []
        final_code = 0

        for name, script in existing:
            result = RUNNER.run(
                name,
                RUNNER.script_command(script),
                timeout_seconds=3_600,
            )
            combined.append(
                f"\n===== {name} =====\n{result.output}"
            )
            final_code = max(final_code, result.return_code)

        synthetic = CommandResult(
            name="Selected regression tests",
            command=["multiple test scripts"],
            started_at=datetime.now().isoformat(),
            finished_at=datetime.now().isoformat(),
            duration_seconds=0.0,
            return_code=final_code,
            output="".join(combined),
        )
        render_result(synthetic)


def render_reports() -> None:
    st.subheader("Generated reports")

    reports = discover_reports(REPO_ROOT)
    if not reports:
        st.info("No supported files were found under reports/.")
        return

    frame = pd.DataFrame(
        [
            {
                "Report": item.relative_path,
                "Type": item.suffix,
                "Size KB": round(item.size_bytes / 1024, 1),
                "Modified": datetime.fromtimestamp(
                    item.modified_timestamp
                ),
            }
            for item in reports
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
    )

    selected_name = st.selectbox(
        "Preview report",
        [item.relative_path for item in reports],
    )
    selected = next(
        item
        for item in reports
        if item.relative_path == selected_name
    )

    data = selected.path.read_bytes()
    st.download_button(
        "Download selected report",
        data=data,
        file_name=selected.path.name,
        mime="application/octet-stream",
        use_container_width=True,
    )

    if selected.suffix == ".html":
        components.html(
            read_text_file(selected.path),
            height=720,
            scrolling=True,
        )
    elif selected.suffix == ".csv":
        try:
            st.dataframe(
                pd.read_csv(selected.path),
                use_container_width=True,
            )
        except Exception:
            st.code(
                read_text_file(selected.path),
                language="text",
            )
    elif selected.suffix == ".json":
        try:
            st.json(
                json.loads(read_text_file(selected.path))
            )
        except json.JSONDecodeError:
            st.code(
                read_text_file(selected.path),
                language="json",
            )
    else:
        st.code(
            read_text_file(selected.path),
            language="text",
        )


def render_history() -> None:
    st.subheader("UI command history")
    history = RUNNER.read_history(limit=100)

    if not history:
        st.info("No UI commands have been run yet.")
        return

    frame = pd.DataFrame(
        [
            {
                "Started": record.get("started_at"),
                "Action": record.get("name"),
                "Succeeded": record.get("succeeded"),
                "Exit": record.get("return_code"),
                "Duration": record.get("duration_seconds"),
                "Command": RUNNER.display_command(
                    record.get("command", [])
                ),
            }
            for record in history
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
    )

    selected = st.selectbox(
        "Command output",
        range(len(history)),
        format_func=lambda index: (
            f"{history[index].get('started_at')} — "
            f"{history[index].get('name')}"
        ),
    )
    st.code(
        history[selected].get("output", ""),
        language="text",
    )


def main() -> None:
    st.set_page_config(
        page_title="Trading AI Control Center",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    initialize_state()

    st.title("Trading AI Control Center")
    st.caption(
        "Local command, scanning, paper-trading, testing, "
        "and report interface."
    )

    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Page",
            [
                "Overview",
                "Market ingestion",
                "Feature generation",
                "Trade scanner",
                "Paper trading",
                "Tests",
                "Reports",
                "Command history",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption(f"Repository: {REPO_ROOT}")
        st.caption(f"Python: {sys.executable}")

    pages: dict[str, Callable[[], None]] = {
        "Overview": render_overview,
        "Market ingestion": render_ingestion,
        "Feature generation": render_features,
        "Trade scanner": render_scanner,
        "Paper trading": render_paper_trading,
        "Tests": render_tests,
        "Reports": render_reports,
        "Command history": render_history,
    }
    pages[page]()


if __name__ == "__main__":
    main()
