from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/trading_ai/ui/app.py"
INDEX = ROOT / "src/trading_ai/ui/static/index.html"


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".m33_phase1.bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def patch_app() -> None:
    text = APP.read_text(encoding="utf-8")
    import_line = (
        "from trading_ai.ui.api.workspaces import router as workspaces_router\n"
    )
    if import_line not in text:
        marker = "from trading_ai.ui.api.workstation_release import router as workstation_release_router\n"
        if marker not in text:
            raise RuntimeError("Unable to locate workstation_release import in app.py")
        text = text.replace(marker, marker + import_line)

    if "workspaces_router," not in text:
        marker = "  workstation_release_router,\n"
        if marker not in text:
            raise RuntimeError("Unable to locate router registration in app.py")
        text = text.replace(marker, marker + "  workspaces_router,\n")

    text = text.replace('version="32.4.0"', 'version="33.1.0"')
    backup(APP)
    APP.write_text(text, encoding="utf-8")


def patch_index() -> None:
    text = INDEX.read_text(encoding="utf-8")
    css = '<link rel="stylesheet" href="/static/workspace.css">'
    js = '<script src="/static/workspace.js"></script>'
    if css not in text:
        text = text.replace("</head>", f"  {css}\n</head>")
    if js not in text:
        text = text.replace("</body>", f"  {js}\n</body>")
    backup(INDEX)
    INDEX.write_text(text, encoding="utf-8")


def main() -> None:
    if not APP.exists() or not INDEX.exists():
        raise SystemExit("Run this installer from the TradingPlatform repository.")
    patch_app()
    patch_index()
    print("Milestone 33 Phase 1 integration completed.")
    print(f"Patched: {APP}")
    print(f"Patched: {INDEX}")


if __name__ == "__main__":
    main()
