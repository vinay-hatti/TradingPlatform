from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .decision_journal_policy import DecisionJournalPolicy
from .decision_journal_profile import (
    DecisionJournalEntryProfile,
    DecisionJournalProfile,
    DecisionReviewProfile,
    ThesisRevisionProfile,
)


class DecisionJournalEngine:
    def __init__(
        self,
        policy: DecisionJournalPolicy | None = None,
    ) -> None:
        self.policy = policy or DecisionJournalPolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _datetime(value: datetime | str | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _revision(
        self,
        source: Any,
        index: int,
    ) -> ThesisRevisionProfile:
        return ThesisRevisionProfile(
            revision_id=str(
                self._get(source, "revision_id", f"REV-{index}")
            ),
            revised_at=self._datetime(
                self._get(source, "revised_at", None)
            ),
            previous_thesis=str(
                self._get(source, "previous_thesis", "")
            ),
            revised_thesis=str(
                self._get(source, "revised_thesis", "")
            ),
            revision_reason=str(
                self._get(source, "revision_reason", "")
            ),
            author=str(self._get(source, "author", "UNKNOWN")),
            material_change=bool(
                self._get(source, "material_change", False)
            ),
        )

    def _review(
        self,
        source: Any,
        index: int,
    ) -> DecisionReviewProfile:
        return DecisionReviewProfile(
            review_id=str(
                self._get(source, "review_id", f"REVIEW-{index}")
            ),
            reviewer=str(
                self._get(source, "reviewer", "UNKNOWN")
            ),
            reviewed_at=self._datetime(
                self._get(source, "reviewed_at", None)
            ),
            review_status=str(
                self._get(source, "review_status", "PENDING")
            ).upper(),
            reviewer_confidence=float(
                self._get(source, "reviewer_confidence", 0.0)
            ),
            comments=str(
                self._get(source, "comments", "")
            ),
            required_actions=tuple(
                str(item)
                for item in self._get(
                    source, "required_actions", ()
                ) or ()
            ),
            execution_approved=bool(
                self._get(source, "execution_approved", False)
            ),
        )

    def build(
        self,
        *,
        journal_id: str,
        research_case: Any,
        scenario_comparison: Any,
        actor: str,
        decision_rationale: str,
        primary_risks: Iterable[str],
        monitoring_plan: Iterable[str],
        reviews: Iterable[Any] = (),
        thesis_revisions: Iterable[Any] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DecisionJournalProfile:
        case_id = str(
            self._get(research_case, "case_id", "UNKNOWN")
        )
        symbol = str(
            self._get(research_case, "symbol", "UNKNOWN")
        )
        strategy_name = str(
            self._get(research_case, "strategy_name", "UNKNOWN")
        )
        current_thesis = str(
            self._get(research_case, "primary_thesis", "")
        )
        recommendation = self._get(
            scenario_comparison, "recommendation", {}
        )
        decision_action = str(
            self._get(recommendation, "action", "MONITOR")
        ).upper()
        decision_confidence = float(
            self._get(recommendation, "confidence", 0.0)
        )
        selected_scenario_id = self._get(
            scenario_comparison, "best_scenario_id", None
        )

        review_profiles = tuple(
            self._review(item, index)
            for index, item in enumerate(reviews, start=1)
        )
        revision_profiles = tuple(
            self._revision(item, index)
            for index, item in enumerate(
                thesis_revisions, start=1
            )
        )

        warnings: list[str] = []
        rejections: list[str] = []
        remediation: list[str] = []
        positives: list[str] = []

        if (
            self.policy.require_decision_rationale
            and not decision_rationale.strip()
        ):
            rejections.append("Decision rationale is required.")
            remediation.append(
                "Document the decision rationale."
            )
        else:
            positives.append("Decision rationale documented")

        risk_tuple = tuple(str(item) for item in primary_risks)
        if self.policy.require_primary_risk and not risk_tuple:
            rejections.append("Primary risks are required.")
            remediation.append(
                "Document material decision risks."
            )
        else:
            positives.append("Primary risks documented")

        monitoring_tuple = tuple(
            str(item) for item in monitoring_plan
        )
        if (
            self.policy.require_monitoring_plan
            and not monitoring_tuple
        ):
            rejections.append("Monitoring plan is required.")
            remediation.append(
                "Document post-decision monitoring requirements."
            )
        else:
            positives.append("Monitoring plan documented")

        if (
            decision_confidence
            < self.policy.minimum_decision_confidence
        ):
            warnings.append(
                "Decision confidence is below policy threshold."
            )
            remediation.append(
                "Strengthen the research case or reduce conviction."
            )
        else:
            positives.append("Decision confidence meets policy")

        for revision in revision_profiles:
            if (
                self.policy.require_thesis_revision_reason
                and not revision.revision_reason.strip()
            ):
                warnings.append(
                    f"Thesis revision {revision.revision_id} "
                    "has no revision reason."
                )
                remediation.append(
                    "Document a reason for every thesis revision."
                )
            if revision.revised_thesis.strip():
                current_thesis = revision.revised_thesis

        approved_reviews = [
            item
            for item in review_profiles
            if item.review_status == "APPROVED"
            and item.execution_approved
            and (
                item.reviewer_confidence
                >= self.policy.minimum_reviewer_confidence
            )
        ]
        rejected_reviews = [
            item
            for item in review_profiles
            if item.review_status == "REJECTED"
        ]
        pending_reviews = [
            item
            for item in review_profiles
            if item.review_status in {"PENDING", "CHANGES_REQUIRED"}
        ]

        if rejected_reviews:
            approval_status = "REJECTED"
            rejections.append(
                "One or more research reviews rejected the decision."
            )
            remediation.append(
                "Resolve review rejection reasons before execution."
            )
        elif approved_reviews:
            self_approvals = [
                item
                for item in approved_reviews
                if item.reviewer == actor
            ]
            if self_approvals and not self.policy.allow_self_approval:
                approval_status = "INVALID_SELF_APPROVAL"
                rejections.append(
                    "Self-approval is prohibited by policy."
                )
                remediation.append(
                    "Obtain approval from an independent reviewer."
                )
            else:
                approval_status = "APPROVED"
                positives.append("Independent review approved")
        elif pending_reviews:
            approval_status = "PENDING_REVIEW"
            warnings.append("Decision review remains pending.")
            remediation.append(
                "Complete the outstanding research review."
            )
        else:
            approval_status = "NOT_REVIEWED"
            if self.policy.require_review_for_execution:
                warnings.append(
                    "Independent review is required for execution."
                )
                remediation.append(
                    "Submit the decision for independent review."
                )

        execution_candidate = decision_action in {
            "STRONG_BUY",
            "BUY",
            "OPPORTUNISTIC_BUY",
        }
        execution_allowed = (
            execution_candidate
            and approval_status == "APPROVED"
            and not rejections
        )

        if execution_allowed:
            decision_status = "APPROVED_FOR_EXECUTION"
        elif rejections:
            decision_status = "REJECTED"
        elif approval_status in {
            "NOT_REVIEWED",
            "PENDING_REVIEW",
        }:
            decision_status = "REVIEW_REQUIRED"
        elif decision_action in {"MONITOR", "WAIT"}:
            decision_status = "MONITORING"
        else:
            decision_status = "HELD"

        now = datetime.now(timezone.utc)
        entries: list[DecisionJournalEntryProfile] = [
            DecisionJournalEntryProfile(
                entry_id=f"{journal_id}-ENTRY-001",
                entry_type="DECISION_CREATED",
                recorded_at=now,
                actor=actor,
                summary=(
                    f"Decision journal created with action "
                    f"{decision_action}."
                ),
                details=decision_rationale,
                prior_status=None,
                resulting_status=decision_status,
                metadata={
                    "selected_scenario_id": selected_scenario_id,
                    "approval_status": approval_status,
                },
            )
        ]

        for index, revision in enumerate(
            revision_profiles, start=2
        ):
            entries.append(
                DecisionJournalEntryProfile(
                    entry_id=f"{journal_id}-ENTRY-{index:03d}",
                    entry_type="THESIS_REVISED",
                    recorded_at=revision.revised_at,
                    actor=revision.author,
                    summary=(
                        f"Thesis revision {revision.revision_id} "
                        "recorded."
                    ),
                    details=revision.revision_reason,
                    prior_status=decision_status,
                    resulting_status=decision_status,
                    metadata={
                        "material_change": revision.material_change
                    },
                )
            )

        offset = len(entries) + 1
        for index, review in enumerate(
            review_profiles, start=offset
        ):
            entries.append(
                DecisionJournalEntryProfile(
                    entry_id=f"{journal_id}-ENTRY-{index:03d}",
                    entry_type="REVIEW_RECORDED",
                    recorded_at=review.reviewed_at,
                    actor=review.reviewer,
                    summary=(
                        f"Review {review.review_id}: "
                        f"{review.review_status}."
                    ),
                    details=review.comments,
                    prior_status=decision_status,
                    resulting_status=decision_status,
                    metadata={
                        "execution_approved": (
                            review.execution_approved
                        ),
                        "reviewer_confidence": (
                            review.reviewer_confidence
                        ),
                    },
                )
            )

        return DecisionJournalProfile(
            journal_id=journal_id,
            case_id=case_id,
            symbol=symbol,
            strategy_name=strategy_name,
            decision_action=decision_action,
            decision_status=decision_status,
            decision_confidence=round(
                decision_confidence, 6
            ),
            decision_rationale=decision_rationale,
            primary_risks=risk_tuple,
            monitoring_plan=monitoring_tuple,
            selected_scenario_id=selected_scenario_id,
            execution_allowed=execution_allowed,
            approval_status=approval_status,
            current_thesis=current_thesis,
            thesis_revisions=revision_profiles,
            reviews=review_profiles,
            entries=tuple(entries),
            positive_factors=tuple(dict.fromkeys(positives)),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            remediation_actions=tuple(
                dict.fromkeys(remediation)
            ),
            metadata={
                "milestone": 34,
                "phase": 4,
                "step": 3,
                "source": "DECISION_JOURNAL_REVIEW_WORKFLOW",
                **dict(metadata or {}),
            },
        )
