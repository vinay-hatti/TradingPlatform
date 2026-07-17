from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .order_linkage_profile import OrderGroupProfile, OrderLinkMember


class JsonOrderGroupRepository:
    def __init__(
        self,
        path: str | Path = "data/order_management/order_groups.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, OrderGroupProfile]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, OrderGroupProfile] = {}
        for group_id, raw in payload.get("groups", {}).items():
            item = dict(raw)
            item["members"] = tuple(
                OrderLinkMember(**member)
                for member in item.get("members", ())
            )
            result[group_id] = OrderGroupProfile(**item)
        return result

    def _save(self, groups: dict[str, OrderGroupProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": {
                group_id: asdict(group)
                for group_id, group in groups.items()
            }
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, group: OrderGroupProfile) -> OrderGroupProfile:
        groups = self._load()
        groups[group.group_id] = group
        self._save(groups)
        return group

    def get(self, group_id: str) -> OrderGroupProfile | None:
        return self._load().get(group_id)

    def require(self, group_id: str) -> OrderGroupProfile:
        group = self.get(group_id)
        if group is None:
            raise KeyError(f"Order group not found: {group_id}")
        return group

    def groups_for_aggregate(
        self,
        aggregate_id: str,
    ) -> tuple[OrderGroupProfile, ...]:
        return tuple(
            group
            for group in self._load().values()
            if any(
                member.aggregate_id == aggregate_id
                for member in group.members
            )
        )
