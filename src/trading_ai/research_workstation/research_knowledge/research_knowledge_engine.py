from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .research_knowledge_policy import ResearchKnowledgePolicy
from .research_knowledge_profile import (
    KnowledgeCaseProfile,
    KnowledgeIndexProfile,
    KnowledgeRecordProfile,
    ResearchKnowledgeBaseProfile,
    ResearchTagProfile,
)


class ResearchKnowledgeEngine:
    def __init__(
        self,
        policy: ResearchKnowledgePolicy | None = None,
    ) -> None:
        self.policy = policy or ResearchKnowledgePolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _tag_key(value: str) -> str:
        return (
            value.strip()
            .lower()
            .replace("/", "_")
            .replace(" ", "_")
        )

    @staticmethod
    def _datetime(value: datetime | str | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def build_case(
        self,
        *,
        research_case: Any,
        scenario_comparison: Any | None = None,
        decision_journal: Any | None = None,
        outcome_attribution: Any | None = None,
        thesis_validation: Any | None = None,
        dashboard_summary: Any | None = None,
        additional_tags: Iterable[Mapping[str, Any]] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> KnowledgeCaseProfile:
        case_id = self._norm(self._get(research_case, "case_id", ""))
        symbol = self._norm(self._get(research_case, "symbol", ""))
        strategy_name = self._norm(
            self._get(research_case, "strategy_name", "UNKNOWN")
        )
        primary_thesis = self._norm(
            self._get(research_case, "primary_thesis", "")
        )
        sector = self._norm(
            self._get(research_case, "sector", "UNSPECIFIED")
        )
        industry = self._norm(
            self._get(research_case, "industry", "UNSPECIFIED")
        )

        decision_action = self._norm(
            self._get(decision_journal, "decision_action", "UNKNOWN")
        )
        decision_status = self._norm(
            self._get(decision_journal, "decision_status", "UNKNOWN")
        )
        outcome_status = self._norm(
            self._get(outcome_attribution, "outcome_status", "UNKNOWN")
        )

        thesis_status = self._norm(
            self._get(
                thesis_validation,
                "validation_status",
                self._get(
                    self._get(
                        outcome_attribution,
                        "thesis_validation",
                        {},
                    ),
                    "validation_status",
                    "UNKNOWN",
                ),
            )
        )

        institutional_score = float(
            self._get(
                dashboard_summary,
                "institutional_score",
                self._get(
                    outcome_attribution,
                    "decision_quality_score",
                    0.0,
                ),
            )
            or 0.0
        )

        evidence = tuple(
            self._get(research_case, "evidence", ()) or ()
        )
        evidence_scores = [
            float(self._get(item, "reliability_score", 0.0) or 0.0)
            for item in evidence
        ]
        evidence_quality = (
            sum(evidence_scores) / len(evidence_scores)
            if evidence_scores
            else 0.0
        )

        field_checks = [
            bool(case_id),
            bool(symbol),
            bool(strategy_name),
            bool(primary_thesis),
            bool(evidence),
            scenario_comparison is not None,
            decision_journal is not None,
            (
                outcome_attribution is not None
                if self.policy.require_outcome_attribution
                else True
            ),
        ]
        completeness = sum(field_checks) / len(field_checks)

        tags: list[ResearchTagProfile] = []

        def add_tag(tag: str, category: str, confidence: float, source: str) -> None:
            normalized = self._tag_key(tag)
            if not normalized:
                return
            if confidence < self.policy.minimum_tag_confidence:
                return
            if any(item.tag == normalized and item.category == category for item in tags):
                return
            tags.append(
                ResearchTagProfile(
                    tag=normalized,
                    category=category,
                    confidence=round(self._clamp(confidence), 6),
                    source=source,
                )
            )

        add_tag(symbol, "SYMBOL", 1.0, "RESEARCH_CASE")
        add_tag(strategy_name, "STRATEGY", 1.0, "RESEARCH_CASE")
        add_tag(sector, "SECTOR", 0.95, "RESEARCH_CASE")
        add_tag(industry, "INDUSTRY", 0.90, "RESEARCH_CASE")
        add_tag(decision_action, "DECISION_ACTION", 0.90, "DECISION_JOURNAL")
        add_tag(outcome_status, "OUTCOME", 0.90, "OUTCOME_ATTRIBUTION")
        add_tag(thesis_status, "THESIS_STATUS", 0.90, "THESIS_VALIDATION")

        for scenario in tuple(self._get(research_case, "scenarios", ()) or ()):
            add_tag(
                self._norm(self._get(scenario, "name", "")),
                "SCENARIO",
                float(self._get(scenario, "probability", 0.5) or 0.5),
                "RESEARCH_CASE",
            )
            for catalyst in tuple(self._get(scenario, "catalysts", ()) or ()):
                add_tag(
                    self._norm(catalyst),
                    "CATALYST",
                    0.75,
                    "RESEARCH_CASE",
                )

        for item in additional_tags:
            add_tag(
                self._norm(item.get("tag")),
                self._norm(item.get("category", "CUSTOM")),
                float(item.get("confidence", 0.5)),
                self._norm(item.get("source", "USER")),
            )

        tags = tags[: self.policy.maximum_tags_per_case]

        records: list[KnowledgeRecordProfile] = []

        def add_record(
            record_id: str,
            record_type: str,
            title: str,
            summary: str,
            source_reference: str,
            quality_score: float,
            record_tags: Iterable[str] = (),
            record_metadata: Mapping[str, Any] | None = None,
        ) -> None:
            if len(records) >= self.policy.maximum_records_per_case:
                return
            records.append(
                KnowledgeRecordProfile(
                    record_id=record_id,
                    record_type=record_type,
                    title=title,
                    summary=summary,
                    source_reference=source_reference,
                    quality_score=round(self._clamp(quality_score), 6),
                    tags=tuple(dict.fromkeys(self._tag_key(x) for x in record_tags if x)),
                    metadata=dict(record_metadata or {}),
                )
            )

        add_record(
            f"{case_id}-THESIS",
            "THESIS",
            "Primary Research Thesis",
            primary_thesis,
            "research_case.json",
            evidence_quality,
            ("thesis", symbol, strategy_name),
        )

        for index, item in enumerate(evidence, start=1):
            add_record(
                f"{case_id}-EVIDENCE-{index:03d}",
                "EVIDENCE",
                self._norm(self._get(item, "title", f"Evidence {index}")),
                self._norm(
                    self._get(
                        item,
                        "summary",
                        self._get(item, "description", ""),
                    )
                ),
                self._norm(
                    self._get(item, "source", "research_case.json")
                ),
                float(self._get(item, "reliability_score", 0.0) or 0.0),
                ("evidence", symbol),
            )

        if scenario_comparison is not None:
            add_record(
                f"{case_id}-SCENARIO-COMPARISON",
                "SCENARIO_COMPARISON",
                "Scenario Comparison",
                f"Best scenario: {self._norm(self._get(scenario_comparison, 'best_scenario_id', 'UNKNOWN'))}",
                "scenario_comparison.json",
                0.85,
                ("scenario", symbol),
            )

        if decision_journal is not None:
            add_record(
                f"{case_id}-DECISION",
                "DECISION_JOURNAL",
                "Decision Journal",
                f"Action={decision_action}; Status={decision_status}",
                "decision_journal.json",
                float(
                    self._get(decision_journal, "decision_confidence", 0.0)
                    or 0.0
                ),
                ("decision", decision_action),
            )

        if outcome_attribution is not None:
            add_record(
                f"{case_id}-OUTCOME",
                "OUTCOME_ATTRIBUTION",
                "Outcome Attribution",
                (
                    f"Outcome={outcome_status}; "
                    f"Realized return={self._get(outcome_attribution, 'realized_return_pct', 0.0)}"
                ),
                "outcome_attribution.json",
                float(
                    self._get(
                        outcome_attribution,
                        "decision_quality_score",
                        0.0,
                    )
                    or 0.0
                ),
                ("outcome", outcome_status, thesis_status),
            )

        warnings: list[str] = []
        rejections: list[str] = []
        remediation: list[str] = []
        positives: list[str] = []

        if self.policy.require_case_id and not case_id:
            rejections.append("Case ID is required.")
            remediation.append("Provide a non-empty case_id.")
        if self.policy.require_symbol and not symbol:
            rejections.append("Symbol is required.")
            remediation.append("Provide a non-empty symbol.")
        if self.policy.require_primary_thesis and not primary_thesis:
            rejections.append("Primary thesis is required.")
            remediation.append("Document the primary thesis.")
        if completeness < self.policy.minimum_case_completeness:
            rejections.append("Case completeness is below policy threshold.")
            remediation.append("Supply all required research artifacts.")
        else:
            positives.append("Case completeness meets policy.")
        if evidence_quality < self.policy.minimum_evidence_quality:
            warnings.append("Evidence quality is below policy threshold.")
            remediation.append("Add stronger and more reliable evidence.")
        else:
            positives.append("Evidence quality meets policy.")
        if not tags:
            warnings.append("No knowledge tags were generated.")
        if not records:
            rejections.append("No knowledge records were generated.")

        return KnowledgeCaseProfile(
            knowledge_case_id=f"KNOWLEDGE-{case_id or 'UNKNOWN'}",
            case_id=case_id or "UNKNOWN",
            symbol=symbol or "UNKNOWN",
            strategy_name=strategy_name or "UNKNOWN",
            sector=sector or "UNSPECIFIED",
            industry=industry or "UNSPECIFIED",
            primary_thesis=primary_thesis,
            decision_action=decision_action or "UNKNOWN",
            decision_status=decision_status or "UNKNOWN",
            outcome_status=outcome_status or "UNKNOWN",
            thesis_validation_status=thesis_status or "UNKNOWN",
            institutional_score=round(self._clamp(institutional_score), 6),
            case_completeness_score=round(completeness, 6),
            evidence_quality_score=round(evidence_quality, 6),
            tags=tuple(tags),
            records=tuple(records),
            positive_factors=tuple(dict.fromkeys(positives)),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            remediation_actions=tuple(dict.fromkeys(remediation)),
            metadata={
                "milestone": 34,
                "phase": 5,
                "step": 1,
                "source": "RESEARCH_KNOWLEDGE_ENGINE",
                **dict(metadata or {}),
            },
        )

    def build_knowledge_base(
        self,
        *,
        knowledge_base_id: str,
        cases: Iterable[KnowledgeCaseProfile],
        generated_at: datetime | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ResearchKnowledgeBaseProfile:
        case_list = list(cases)

        if not self.policy.allow_duplicate_case_ids:
            seen: set[str] = set()
            duplicates: set[str] = set()
            for item in case_list:
                if item.case_id in seen:
                    duplicates.add(item.case_id)
                seen.add(item.case_id)
            if duplicates:
                raise ValueError(
                    "Duplicate case IDs are not allowed: "
                    + ", ".join(sorted(duplicates))
                )

        symbols: defaultdict[str, list[str]] = defaultdict(list)
        sectors: defaultdict[str, list[str]] = defaultdict(list)
        strategies: defaultdict[str, list[str]] = defaultdict(list)
        tags: defaultdict[str, list[str]] = defaultdict(list)
        outcomes: defaultdict[str, list[str]] = defaultdict(list)
        thesis_statuses: defaultdict[str, list[str]] = defaultdict(list)

        for item in case_list:
            symbols[item.symbol].append(item.case_id)
            sectors[item.sector].append(item.case_id)
            strategies[item.strategy_name].append(item.case_id)
            outcomes[item.outcome_status].append(item.case_id)
            thesis_statuses[item.thesis_validation_status].append(item.case_id)
            for tag in item.tags:
                tags[tag.tag].append(item.case_id)

        index = KnowledgeIndexProfile(
            symbols={k: tuple(dict.fromkeys(v)) for k, v in sorted(symbols.items())},
            sectors={k: tuple(dict.fromkeys(v)) for k, v in sorted(sectors.items())},
            strategies={k: tuple(dict.fromkeys(v)) for k, v in sorted(strategies.items())},
            tags={k: tuple(dict.fromkeys(v)) for k, v in sorted(tags.items())},
            outcomes={k: tuple(dict.fromkeys(v)) for k, v in sorted(outcomes.items())},
            thesis_statuses={
                k: tuple(dict.fromkeys(v))
                for k, v in sorted(thesis_statuses.items())
            },
        )

        warnings = tuple(
            f"Case {item.case_id}: {warning}"
            for item in case_list
            for warning in item.warnings
        )
        rejections = tuple(
            f"Case {item.case_id}: {reason}"
            for item in case_list
            for reason in item.rejection_reasons
        )
        governance_status = "REJECTED" if rejections else "READY"

        return ResearchKnowledgeBaseProfile(
            knowledge_base_id=knowledge_base_id,
            generated_at=self._datetime(generated_at),
            case_count=len(case_list),
            record_count=sum(len(item.records) for item in case_list),
            tag_count=sum(len(item.tags) for item in case_list),
            cases=tuple(case_list),
            index=index,
            governance_status=governance_status,
            warnings=warnings,
            rejection_reasons=rejections,
            metadata={
                "milestone": 34,
                "phase": 5,
                "step": 1,
                "source": "RESEARCH_KNOWLEDGE_ENGINE",
                **dict(metadata or {}),
            },
        )
