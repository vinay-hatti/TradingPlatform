from types import SimpleNamespace

from trading_ai.scanner.dashboard.ranking_cli import _invoke_service


class BuildService:
    def build(self, records, query):
        return {
            "total_records": len(records),
            "query": query,
        }


class RunService:
    def run(self, opportunities, request):
        return SimpleNamespace(
            total_records=len(opportunities),
            request=request,
        )


def main() -> None:
    records = [object(), object()]
    query = object()

    first = _invoke_service(BuildService(), records, query)
    assert first["total_records"] == 2

    second = _invoke_service(RunService(), records, query)
    assert second.total_records == 2

    print(
        "Milestone 35 Phase 5 Step 3 service compatibility assertions passed."
    )


if __name__ == "__main__":
    main()
