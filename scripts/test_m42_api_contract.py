#import sys
#from pathlib import Path
#sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
#from trading_ai.production_api.app import create_production_app
#paths={r.path for r in create_production_app().routes}
#for p in ['/api/v1/realtime/snapshot','/api/v1/realtime/alerts','/api/v1/realtime/events','/api/v1/realtime/stream']: assert p in paths,p
#print('Milestone 42 API contract assertions passed.')

from trading_ai.production_api.app import create_production_app


def collect_routes(routes):
    collected = set()

    for route in routes:
        path = getattr(route, "path", None)
        if path:
            collected.add(path)

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            collected.update(
                collect_routes(original_router.routes)
            )

        mounted_app = getattr(route, "app", None)
        mounted_routes = getattr(mounted_app, "routes", None)
        if mounted_routes is not None:
            collected.update(
                collect_routes(mounted_routes)
            )

    return collected


app = create_production_app()

paths = collect_routes(app.routes)

required = {
    "/api/v1/realtime/snapshot",
    "/api/v1/realtime/alerts",
    "/api/v1/realtime/events",
    "/api/v1/realtime/stream",
}

missing = required - paths

assert not missing, f"Missing routes: {sorted(missing)}"

print("Milestone 42 API contract assertions passed.")
