from __future__ import annotations

from .walk_forward_policy import WalkForwardPolicy
from .walk_forward_profile import WalkForwardWindow


class InstitutionalWalkForwardSplitter:
    def __init__(self, policy: WalkForwardPolicy | None = None) -> None:
        self.policy = policy or WalkForwardPolicy()

    def split(self, observation_count: int) -> list[WalkForwardWindow]:
        p = self.policy
        windows: list[WalkForwardWindow] = []
        anchor = 0
        train_end = p.train_size
        index = 1

        while True:
            train_start = 0 if p.anchored_training else anchor
            validation_start = train_end + p.purge_size
            validation_end = validation_start + p.validation_size
            test_start = validation_end + p.embargo_size
            test_end = test_start + p.test_size
            if test_end > observation_count:
                break
            windows.append(WalkForwardWindow(
                window_id=f"WF_{index:03d}",
                train_start=train_start,
                train_end=train_end,
                validation_start=validation_start,
                validation_end=validation_end,
                test_start=test_start,
                test_end=test_end,
                purge_size=p.purge_size,
                embargo_size=p.embargo_size,
            ))
            index += 1
            anchor += p.step_size
            train_end += p.step_size
        return windows
