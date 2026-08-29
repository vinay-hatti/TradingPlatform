from trading_ai.production_api.app import create_production_app


def collect(routes):
    paths=set()
    for route in routes:
        path=getattr(route,'path',None)
        if path: paths.add(path)
        original=getattr(route,'original_router',None)
        if original is not None: paths.update(collect(getattr(original,'routes',[])))
    return paths

paths=collect(create_production_app().routes)
required={
    '/api/v1/scanner/runs',
    '/api/v1/scanner/runs/{run_id}',
    '/api/v1/scanner/runs/{run_id}/results',
    '/api/v1/scanner/data-refresh',
}
assert required <= paths, sorted(required-paths)
print('Milestone 43 API contract assertions passed.')
