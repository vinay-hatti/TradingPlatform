from __future__ import annotations


class OrderRepositoryError(RuntimeError):
    pass


class OrderNotFoundError(OrderRepositoryError):
    pass


class DuplicateOrderError(OrderRepositoryError):
    pass


class DuplicateOrderEventError(OrderRepositoryError):
    pass


class OptimisticConcurrencyError(OrderRepositoryError):
    def __init__(
        self,
        aggregate_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        super().__init__(
            f"Optimistic concurrency conflict for {aggregate_id}: "
            f"expected version {expected_version}, actual version {actual_version}"
        )
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class AuditLedgerIntegrityError(OrderRepositoryError):
    pass
