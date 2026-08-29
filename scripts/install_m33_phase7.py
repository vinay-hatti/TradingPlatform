from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/trading_ai/ui/app.py"
INDEX = ROOT / "src/trading_ai/ui/static/index.html"


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".m33_phase7.bak")
    if not target.exists():
        shutil.copy2(path, target)


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    import_line = (
        "from trading_ai.ui.api.operations_command_center "
        "import router as operations_command_center_router\n"
    )
    if import_line not in text:
        anchors = [
            "from trading_ai.ui.api.strategy_studio import router as strategy_studio_router\n",
            "from trading_ai.ui.api.admin_runtime import router as admin_runtime_router\n",
        ]
        marker = next((item for item in anchors if item in text), None)
        if marker is None:
            raise RuntimeError("Unable to locate UI router import anchor")
        text = text.replace(marker, marker + import_line)

    if "operations_command_center_router," not in text:
        anchors = ["  strategy_studio_router,\n", "  admin_runtime_router,\n"]
        marker = next((item for item in anchors if item in text), None)
        if marker is None:
            raise RuntimeError("Unable to locate router registration anchor")
        text = text.replace(marker, marker + "  operations_command_center_router,\n")

    text = text.replace('version="33.6.0"', 'version="33.7.0"')
    backup(APP)
    APP.write_text(text, encoding="utf-8")

    html = INDEX.read_text(encoding="utf-8")
    script = '<script src="/static/operations_command_center.js"></script>'
    if script not in html:
        html = html.replace("</body>", f"  {script}\n</body>")
    backup(INDEX)
    INDEX.write_text(html, encoding="utf-8")
    print("Milestone 33 Phase 7 integration completed.")


if __name__ == "__main__":
    main()
