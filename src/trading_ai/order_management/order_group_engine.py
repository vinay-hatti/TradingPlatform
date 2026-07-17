from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .order_linkage_policy import OrderLinkagePolicy
from .order_linkage_profile import (
    OrderGroupDecision,
    OrderGroupProfile,
    OrderLinkMember,
    OrderLinkageCheck,
)
from .order_profile import CanonicalOrderAggregate


class OrderGroupEngine:
    def __init__(self, policy: OrderLinkagePolicy | None = None) -> None:
        self.policy = policy or OrderLinkagePolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def create_group(
        self,
        *,
        group_id: str,
        group_type: str,
        aggregates: Iterable[CanonicalOrderAggregate],
        roles: dict[str, str],
    ) -> OrderGroupDecision:
        items = tuple(aggregates)
        checks: list[OrderLinkageCheck] = []

        def add(name: str, passed: bool, message: str, metadata=None) -> None:
            checks.append(
                OrderLinkageCheck(
                    name=name,
                    passed=bool(passed),
                    required=True,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        normalized_type = group_type.strip().upper()
        ids = [item.aggregate_id for item in items]
        add("group_id", bool(group_id), "Group id is required.")
        add(
            "group_type",
            normalized_type in self.policy.allowed_group_types,
            "Group type is supported.",
        )
        add(
            "member_count",
            1 < len(items) <= self.policy.maximum_group_members,
            "Group member count is within policy.",
        )
        add(
            "duplicate_members",
            not self.policy.reject_duplicate_members
            or len(ids) == len(set(ids)),
            "Group members must be unique.",
        )

        accounts = {item.account_id for item in items}
        add(
            "same_account",
            len(accounts) <= 1 or not self.policy.require_same_account,
            "Group members must share the same account.",
        )

        roots = {
            item.root_aggregate_id or item.aggregate_id
            for item in items
        }
        add(
            "same_root",
            len(roots) <= 1 or not self.policy.require_same_root_aggregate,
            "Group members must share the same root aggregate.",
        )

        if normalized_type == "OCO":
            add(
                "oco_member_count",
                len(items) == 2
                or not self.policy.require_exactly_two_oco_members,
                "OCO groups require exactly two members.",
            )

        if normalized_type == "BRACKET":
            role_values = {roles.get(item.aggregate_id, "").upper() for item in items}
            add(
                "bracket_structure",
                (
                    not self.policy.require_bracket_entry_and_two_exits
                    or (
                        len(items) == 3
                        and "ENTRY" in role_values
                        and "TAKE_PROFIT" in role_values
                        and "STOP_LOSS" in role_values
                    )
                ),
                "Bracket requires entry, take-profit, and stop-loss members.",
            )

        if normalized_type == "PARENT_CHILD":
            parents = [
                item for item in items
                if roles.get(item.aggregate_id, "").upper() == "PARENT"
            ]
            children = [
                item for item in items
                if roles.get(item.aggregate_id, "").upper() == "CHILD"
            ]
            add(
                "parent_child_structure",
                len(parents) == 1
                and 0 < len(children) <= self.policy.maximum_children_per_parent,
                "Parent/child group requires one parent and valid children.",
            )

        required = [item for item in checks if item.required]
        failed = [item for item in required if not item.passed]
        score = (
            sum(item.score for item in required) / len(required)
            if required else 100.0
        )
        allowed = not failed
        if not self.policy.fail_closed:
            allowed = normalized_type in self.policy.allowed_group_types

        grade, severity = self._grade(score)
        group = None
        if allowed:
            now = datetime.now(timezone.utc).isoformat()
            root = next(iter(roots))
            account = next(iter(accounts))
            group = OrderGroupProfile(
                group_id=group_id,
                group_type=normalized_type,
                account_id=account,
                root_aggregate_id=root,
                members=tuple(
                    OrderLinkMember(
                        aggregate_id=item.aggregate_id,
                        role=roles.get(item.aggregate_id, "MEMBER").upper(),
                        activation_state=(
                            "ACTIVE"
                            if roles.get(item.aggregate_id, "").upper()
                            in {"PARENT", "ENTRY"}
                            or normalized_type == "OCO"
                            else "PENDING"
                        ),
                    )
                    for item in items
                ),
                created_at=now,
                updated_at=now,
            )

        return OrderGroupDecision(
            valid=True,
            allowed=allowed,
            action="CREATE_GROUP",
            group=group,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="USE_GROUP" if allowed else "REJECT",
            checks=tuple(checks),
            rejection_reasons=tuple(
                item.name.upper() for item in failed
            ),
        )
