from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .filter_contracts import SavedScannerView


class SavedScannerViewRepository:
    def __init__(
        self,
        path: Path | str = Path(
            "reports/m35/phase5/dashboard/saved_views.json"
        ),
    ) -> None:
        self.path = Path(path)

    def list_views(self) -> list[SavedScannerView]:
        payload = self._load_payload()
        return [
            SavedScannerView.from_dict(item)
            for item in payload.get("views", [])
        ]

    def get(self, name: str) -> SavedScannerView:
        normalized = name.strip().lower()
        for view in self.list_views():
            if view.name.strip().lower() == normalized:
                return view
        raise KeyError(f"Saved scanner view not found: {name}")

    def upsert(self, view: SavedScannerView) -> SavedScannerView:
        views = self.list_views()
        normalized = view.name.strip().lower()
        updated: list[SavedScannerView] = []
        replaced = False
        for existing in views:
            if existing.name.strip().lower() == normalized:
                updated.append(view)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(view)
        updated.sort(key=lambda item: item.name.lower())
        self._write(updated)
        return view

    def delete(self, name: str) -> bool:
        normalized = name.strip().lower()
        views = self.list_views()
        retained = [
            view
            for view in views
            if view.name.strip().lower() != normalized
        ]
        if len(retained) == len(views):
            return False
        self._write(retained)
        return True

    def _load_payload(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "views": []}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return {"schema_version": 1, "views": payload}
        if not isinstance(payload, dict):
            raise ValueError(
                f"Invalid saved-view registry: {self.path}"
            )
        payload.setdefault("schema_version", 1)
        payload.setdefault("views", [])
        return payload

    def _write(self, views: list[SavedScannerView]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "views": [view.to_dict() for view in views],
        }

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()
