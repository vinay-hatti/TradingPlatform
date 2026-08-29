from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from trading_ai.production_api.app import create_production_app
from trading_ai.ui.workstation import mount_workstation


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parent


def create_app():
    application = create_production_app()
    application.title = "Trading AI Institutional Workstation"
    application.version = "41.0.1"
    mount_workstation(application, repository_root=REPOSITORY_ROOT)
    return application


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Milestone 41 institutional workstation"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.reload:
        # Reload mode requires an import string. scripts/ is intentionally not a
        # Python package, so expose its directory through app_dir and import the
        # launcher as a top-level module.
        uvicorn.run(
            "run_m41_workstation:app",
            app_dir=str(SCRIPT_DIR),
            host=args.host,
            port=args.port,
            reload=True,
        )
        return

    # Passing the FastAPI object directly avoids importing a non-package path
    # such as scripts.run_m41_workstation.
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
