from __future__ import annotations

import ast
import compileall
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MIGRATIONS = ROOT / "migrations" / "versions"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def validate_migration_graph() -> None:
    revisions: dict[str, str] = {}
    parents_by_revision: dict[str, object] = {}
    for path in MIGRATIONS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    try:
                        values[target.id] = ast.literal_eval(value)
                    except (ValueError, TypeError):
                        pass
        revision = values.get("revision")
        if isinstance(revision, str):
            revisions[revision] = path.name
            parents_by_revision[revision] = values.get("down_revision")

    referenced: set[str] = set()
    missing: list[tuple[str, str]] = []
    for revision, parent_value in parents_by_revision.items():
        parents = parent_value if isinstance(parent_value, (tuple, list)) else [parent_value]
        for parent in parents:
            if not parent:
                continue
            referenced.add(parent)
            if parent not in revisions:
                missing.append((revision, parent))

    heads = sorted(set(revisions) - referenced)
    if missing:
        raise RuntimeError(f"Alembic revisions have missing parents: {missing}")
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, found {heads or 'none'}")
    print(f"Alembic graph: {len(revisions)} revisions, head={heads[0]}")


def local_module_path(module) -> Path:
    value = getattr(module, "__file__", None)
    if not value:
        raise RuntimeError(f"Module {module.__name__} has no __file__")
    return Path(value).resolve()


def validate_routes() -> None:
    from trading_ai.production_api.app import create_production_app

    application = create_production_app()

    def collect_routes(routes) -> set[str]:
        collected: set[str] = set()

        for route in routes:
            path = getattr(route, "path", None)
            if path:
                collected.add(path)

            # FastAPI >= 0.137 stores included routers lazily as
            # fastapi.routing._IncludedRouter instances.
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                collected.update(
                    collect_routes(getattr(original_router, "routes", []))
                )

            # Retain support for standard Starlette/FastAPI mounted apps.
            mounted_app = getattr(route, "app", None)
            mounted_routes = getattr(mounted_app, "routes", None)
            if mounted_routes is not None:
                collected.update(collect_routes(mounted_routes))

        return collected

    actual_routes = collect_routes(application.routes)

    required_routes = {
        "/api/v1/platform/health",
        "/api/v1/platform/readiness",
        "/api/v1/platform/overview",
        "/api/v1/realtime/snapshot",
        "/api/v1/realtime/stream",
    }

    missing_routes = required_routes - actual_routes
    if missing_routes:
        raise RuntimeError(
            "Production app is missing required routes. "
            f"Missing={sorted(missing_routes)}; "
            f"actual={sorted(actual_routes)}"
        )

    print(
        f"Production API: {len(actual_routes)} routes; "
        "required HTTP and WebSocket routes verified"
    )





def main() -> None:
    print("TradingPlatform v1.0 RC1 validation")
    if not compileall.compile_dir(SRC, quiet=1):
        raise RuntimeError("src compilation failed")
    if not compileall.compile_dir(ROOT / "scripts", quiet=1):
        raise RuntimeError("scripts compilation failed")
    validate_migration_graph()
    validate_routes()

    tests = []
    for milestone in range(36, 43):
        tests.extend(sorted(ROOT.glob(f"scripts/test_m{milestone}*.py")))
    for test in tests:
        run([sys.executable, str(test)])
    print(f"Python regression scripts: {len(tests)} passed")

    workstation = ROOT / "ui" / "workstation"
    if (workstation / "node_modules").is_dir():
        run(["npm", "run", "test"], cwd=workstation)
        run(["npm", "run", "typecheck"], cwd=workstation)
        run(["npm", "run", "build"], cwd=workstation)
    else:
        print("Frontend dependency validation skipped: run npm install in ui/workstation first.")

    print("TradingPlatform v1.0 RC1 validation passed.")


if __name__ == "__main__":
    main()
