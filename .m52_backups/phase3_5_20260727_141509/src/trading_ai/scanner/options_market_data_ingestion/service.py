from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from trading_ai.scanner.options_market_data_quality.deduplication import (
    OptionContractDeduplicator,
)
from trading_ai.scanner.options_market_data_quality.policy import (
    OptionContractValidationPolicy,
)
from trading_ai.scanner.options_market_data_quality.validation import (
    OptionContractValidationEngine,
)

from .contracts import (
    IngestionBatchResult,
    IngestionRunProfile,
    OptionHistoryProvider,
)
from .manifest import IngestionManifestStore
from .persistence import OptionHistoryWriter


class OptionHistoryIngestionService:
    def __init__(
        self,
        database: Session | Engine,
        provider: OptionHistoryProvider,
        *,
        manifest_store: IngestionManifestStore,
        validation_policy: OptionContractValidationPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.manifest_store = manifest_store
        self.validation_engine = OptionContractValidationEngine(
            validation_policy
        )
        self.deduplicator = OptionContractDeduplicator()
        self.writer = OptionHistoryWriter(database)

    def run(
        self,
        *,
        symbols: Sequence[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        batch_size: int = 5_000,
        resume: bool = True,
        fail_fast: bool = False,
    ) -> IngestionRunProfile:
        started = datetime.now(timezone.utc)
        results: list[IngestionBatchResult] = []
        resumed_batches = 0
        failed_batches = 0

        for batch in self.provider.iter_batches(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            batch_size=batch_size,
        ):
            if resume and self.manifest_store.is_completed(batch.batch_id):
                resumed_batches += 1
                continue

            try:
                deduplicated = self.deduplicator.deduplicate(batch.records)
                validations = self.validation_engine.evaluate_many(
                    deduplicated.records
                )
                valid_records = tuple(
                    result.record for result in validations if result.valid
                )
                rejected_count = sum(not result.valid for result in validations)
                write_result = self.writer.write(valid_records)

                batch_result = IngestionBatchResult(
                    batch_id=batch.batch_id,
                    input_records=len(batch.records),
                    valid_records=len(valid_records),
                    rejected_records=rejected_count,
                    inserted_records=write_result.inserted_records,
                    updated_records=write_result.updated_records,
                    skipped_records=(
                        deduplicated.duplicate_record_count
                        + write_result.skipped_records
                    ),
                )
                results.append(batch_result)
                self.manifest_store.mark_completed(
                    batch.batch_id,
                    metadata={
                        "input_records": batch_result.input_records,
                        "valid_records": batch_result.valid_records,
                        "rejected_records": batch_result.rejected_records,
                    },
                )
            except Exception as exc:
                failed_batches += 1
                results.append(
                    IngestionBatchResult(
                        batch_id=batch.batch_id,
                        input_records=len(batch.records),
                        valid_records=0,
                        rejected_records=0,
                        inserted_records=0,
                        updated_records=0,
                        skipped_records=0,
                        error_messages=(str(exc),),
                    )
                )
                if fail_fast:
                    raise

        completed = datetime.now(timezone.utc)
        return IngestionRunProfile(
            source_name=self.provider.source_name,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            batch_count=len(results),
            input_records=sum(item.input_records for item in results),
            valid_records=sum(item.valid_records for item in results),
            rejected_records=sum(item.rejected_records for item in results),
            inserted_records=sum(item.inserted_records for item in results),
            updated_records=sum(item.updated_records for item in results),
            skipped_records=sum(item.skipped_records for item in results),
            resumed_batches=resumed_batches,
            failed_batches=failed_batches,
            batch_results=tuple(results),
            metadata={
                "start_date": start_date,
                "end_date": end_date,
                "batch_size": batch_size,
                "resume": resume,
            },
        )
