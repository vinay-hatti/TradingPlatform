from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from .paper_position_profile import PaperPositionLot, PaperPositionProfile

class JsonPaperPositionRepository:
    def __init__(
        self,
        path: str | Path = "data/paper_trading/positions.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, PaperPositionProfile]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result = {}
        for position_id, raw in payload.get("positions", {}).items():
            item = dict(raw)
            item["lots"] = tuple(
                PaperPositionLot(**lot)
                for lot in item.get("lots", ())
            )
            result[position_id] = PaperPositionProfile(**item)
        return result

    def _save(self, positions: dict[str, PaperPositionProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(
                {"positions": {k: asdict(v) for k, v in positions.items()}},
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def get(self, position_id: str) -> PaperPositionProfile | None:
        return self._load().get(position_id)

    def save(self, position: PaperPositionProfile) -> PaperPositionProfile:
        positions = self._load()
        positions[position.position_id] = position
        self._save(positions)
        return position

    def all(self) -> tuple[PaperPositionProfile, ...]:
        return tuple(self._load().values())

    def open_for_session(self, session_id: str) -> tuple[PaperPositionProfile, ...]:
        return tuple(
            p for p in self._load().values()
            if p.session_id == session_id and p.is_open
        )
