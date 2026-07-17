from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderLinkagePolicy:
    allowed_group_types: tuple[str, ...] = (
        "PARENT_CHILD",
        "BRACKET",
        "OCO",
    )
    activate_children_on_parent_fill: bool = True
    activate_children_on_parent_partial_fill: bool = False
    cancel_oco_siblings_on_fill: bool = True
    cancel_oco_siblings_on_partial_fill: bool = False
    cancel_children_when_parent_canceled: bool = True
    cancel_children_when_parent_rejected: bool = True
    require_same_account: bool = True
    require_same_root_aggregate: bool = True
    require_exactly_two_oco_members: bool = True
    require_bracket_entry_and_two_exits: bool = True
    reject_duplicate_members: bool = True
    reject_terminal_member_activation: bool = True
    maximum_children_per_parent: int = 16
    maximum_group_members: int = 32
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_children_per_parent <= 0:
            raise ValueError("maximum_children_per_parent must be positive")
        if self.maximum_group_members <= 0:
            raise ValueError("maximum_group_members must be positive")
        if not self.allowed_group_types:
            raise ValueError("allowed_group_types cannot be empty")
