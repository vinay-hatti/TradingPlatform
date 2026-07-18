from __future__ import annotations

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters


def main() -> None:
    adapters = RepositoryArtifactAdapters()
    print("Trading AI UI artifact diagnostics")
    print(f"Project root: {adapters.root}")
    print("-" * 72)

    for name, result in adapters.freshness().items():
        status = "AVAILABLE" if result.available else "MISSING"
        print(f"{name:16} {status:10} {result.detail}")
        if result.path:
            print(f"{'':28}{result.path}")
        print(f"{'':28}as_of={result.as_of.isoformat()}")
        print(f"{'':28}latency_ms={result.latency_ms:.2f}")


if __name__ == "__main__":
    main()
