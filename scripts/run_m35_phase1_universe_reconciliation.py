from __future__ import annotations
import argparse
from pathlib import Path

from trading_ai.scanner.universe_management import (
    FileUniverseProvider, NasdaqSymbolDirectoryProvider, UniverseEngine,
    UniversePolicy, UniverseReconciliationService, write_reconciliation_json,
    write_universe_json, write_universe_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile governed universe providers.")
    parser.add_argument("--nasdaq", action="store_true")
    parser.add_argument("--csv", action="append", default=[])
    parser.add_argument("--minimum-symbol-count", type=int, default=6000)
    parser.add_argument("--output-dir", default="reports/m35/phase1/reconciliation")
    args = parser.parse_args()
    providers = []
    if args.nasdaq:
        providers.append(NasdaqSymbolDirectoryProvider())
    providers.extend(FileUniverseProvider(path, name=f"CSV_{index}") for index, path in enumerate(args.csv, 1))
    if not providers:
        parser.error("At least one provider is required: --nasdaq or --csv PATH")

    reconciliation = UniverseReconciliationService().fetch_and_reconcile(providers)
    universe = UniverseEngine(UniversePolicy(minimum_symbol_count=args.minimum_symbol_count)).build(reconciliation.securities)
    output = Path(args.output_dir)
    write_reconciliation_json(reconciliation, output / "provider_reconciliation.json")
    write_universe_json(universe, output / "universe_registry.json")
    write_universe_summary(universe, output / "universe_summary.json")

    print(f"Providers: {', '.join(reconciliation.provider_counts)}")
    print(f"Unique symbols: {len(reconciliation.securities)}")
    print(f"Failed providers: {reconciliation.failed_provider_count}")
    print(f"Conflicts: {reconciliation.conflict_count}")
    print(f"Provider status: {reconciliation.governance_status}")
    print(f"Universe status: {universe.universe.governance_status}")
    for result in reconciliation.provider_results:
        if result.warning:
            print(f"WARNING [{result.provider_name}]: {result.warning}")


if __name__ == "__main__":
    main()
