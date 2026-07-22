from __future__ import annotations

from .filter_contracts import SavedScannerView
from .saved_view_repository import SavedScannerViewRepository


class SavedScannerViewService:
    def __init__(
        self,
        repository: SavedScannerViewRepository | None = None,
    ) -> None:
        self.repository = repository or SavedScannerViewRepository()

    def list_views(self) -> list[SavedScannerView]:
        return self.repository.list_views()

    def load(self, name: str) -> SavedScannerView:
        return self.repository.get(name)

    def save(self, view: SavedScannerView) -> SavedScannerView:
        if not view.name.strip():
            raise ValueError("Saved scanner view name cannot be empty.")
        if view.sort_direction.upper() not in {"ASC", "DESC"}:
            raise ValueError(
                "Saved scanner view sort direction must be ASC or DESC."
            )
        if view.top_n <= 0 or view.page_size <= 0:
            raise ValueError(
                "Saved scanner view top_n and page_size must be positive."
            )
        return self.repository.upsert(view)

    def delete(self, name: str) -> bool:
        return self.repository.delete(name)
