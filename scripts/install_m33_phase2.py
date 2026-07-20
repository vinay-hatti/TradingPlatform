from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/trading_ai/ui/app.py"
INDEX = ROOT / "src/trading_ai/ui/static/index.html"


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".m33_phase2.bak")
    if not target.exists():
        shutil.copy2(path, target)


def patch_app() -> None:
    text = APP.read_text(encoding="utf-8")
    import_line = "from trading_ai.ui.api.option_chain import router as option_chain_router\n"
    if import_line not in text:
        candidates = [
            "from trading_ai.ui.api.workspaces import router as workspaces_router\n",
            "from trading_ai.ui.api.workstation_release import router as workstation_release_router\n",
        ]
        marker = next((item for item in candidates if item in text), None)
        if not marker:
            raise RuntimeError("Unable to locate UI router imports in app.py")
        text = text.replace(marker, marker + import_line)

    if "option_chain_router," not in text:
        candidates = ["  workspaces_router,\n", "  workstation_release_router,\n"]
        marker = next((item for item in candidates if item in text), None)
        if not marker:
            raise RuntimeError("Unable to locate include_router registration in app.py")
        text = text.replace(marker, marker + "  option_chain_router,\n")

    text = text.replace('version="33.1.0"', 'version="33.2.0"')
    backup(APP)
    APP.write_text(text, encoding="utf-8")


def patch_index() -> None:
    text = INDEX.read_text(encoding="utf-8")
    css = '<link rel="stylesheet" href="/static/option_chain.css">'
    js = '<script src="/static/option_chain.js"></script>'
    if css not in text:
        text = text.replace("</head>", f"  {css}\n</head>")
    if js not in text:
        text = text.replace("</body>", f"  {js}\n</body>")
    backup(INDEX)
    INDEX.write_text(text, encoding="utf-8")


def main() -> None:
    if not APP.exists() or not INDEX.exists():
        raise SystemExit("Run from the TradingPlatform repository root.")
    patch_app()
    patch_index()
    print("Milestone 33 Phase 2 integration completed.")
    print(APP)
    print(INDEX)


if __name__ == "__main__":
    main()
