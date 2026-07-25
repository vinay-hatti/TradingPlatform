from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .contracts import DealerPositioningPolicy


@dataclass(frozen=True)
class DealerPositionRefreshResult:
    symbol: str
    status: str
    option_snapshot_date: str | None = None
    source_contract_count: int = 0
    executable_contract_count: int = 0
    positioning_label: str | None = None
    confidence_score: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class DealerPositionRefreshProfile:
    started_at: str
    completed_at: str
    as_of_date: str
    requested_symbols: int
    refreshed_symbols: int
    failed_symbols: int
    skipped_symbols: int
    results: tuple[DealerPositionRefreshResult, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DealerPositionRefreshOrchestrator:
    """Refresh Milestone 44 derived tables after an options snapshot ingestion.

    The normalized tables use (symbol, as_of_date, ...) keys. Repeated runs on the
    same trading day therefore replace the current day's derived state rather than
    creating duplicate rows. This is intentional: these tables represent the latest
    market-structure view for that snapshot date.
    """

    def __init__(
        self,
        policy: DealerPositioningPolicy | None = None,
        *,
        output_dir: Path = Path("reports/m44"),
        write_reports: bool = True,
        service_factory: Callable[[DealerPositioningPolicy], object] | None = None,
    ) -> None:
        self.policy = policy or DealerPositioningPolicy()
        self.output_dir = Path(output_dir)
        self.write_reports = write_reports
        self.service_factory = service_factory

    def run(
        self,
        symbols: Iterable[str],
        as_of: date,
        *,
        continue_on_error: bool = True,
    ) -> DealerPositionRefreshProfile:
        started = datetime.now(timezone.utc)
        normalized = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        results: list[DealerPositionRefreshResult] = []
        if self.service_factory is None:
            from .service import InstitutionalMarketStructureService
            service = InstitutionalMarketStructureService(self.policy)
        else:
            service = self.service_factory(self.policy)

        for symbol in normalized:
            try:
                snapshot = service.run(
                    symbol,
                    as_of,
                    output_dir=self.output_dir,
                    persist=True,
                    write_reports=self.write_reports,
                )
                results.append(
                    DealerPositionRefreshResult(
                        symbol=symbol,
                        status="REFRESHED",
                        option_snapshot_date=snapshot.option_snapshot_date,
                        source_contract_count=snapshot.source_contract_count,
                        executable_contract_count=snapshot.executable_contract_count,
                        positioning_label=snapshot.positioning_label,
                        confidence_score=snapshot.confidence_score,
                    )
                )
            except ValueError as exc:
                # No usable chain/price is an expected per-symbol condition in a large universe.
                results.append(DealerPositionRefreshResult(symbol=symbol, status="SKIPPED", error=str(exc)))
                if not continue_on_error:
                    raise
            except Exception as exc:
                results.append(DealerPositionRefreshResult(symbol=symbol, status="FAILED", error=str(exc)))
                if not continue_on_error:
                    raise

        completed = datetime.now(timezone.utc)
        refreshed = sum(r.status == "REFRESHED" for r in results)
        failed = sum(r.status == "FAILED" for r in results)
        skipped = sum(r.status == "SKIPPED" for r in results)
        return DealerPositionRefreshProfile(
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            as_of_date=as_of.isoformat(),
            requested_symbols=len(normalized),
            refreshed_symbols=refreshed,
            failed_symbols=failed,
            skipped_symbols=skipped,
            results=tuple(results),
        )


def write_refresh_profile(profile: DealerPositionRefreshProfile, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(profile.to_dict(), indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(target)
    return target
