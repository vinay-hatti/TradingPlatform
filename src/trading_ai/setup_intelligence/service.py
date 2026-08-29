from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, func, select

from trading_ai.outcome_probability.models import OutcomeProbabilityObservationModel
from trading_ai.stock_intelligence.models import StockScannerCandidateModel, StockScannerPublicationModel

from .detector import GovernedSetupDetector
from .expected_value import SetupExpectedValueEngine
from .models import (
    SetupCertificationModel, SetupIntelligenceSnapshotModel, SetupProbabilityModelArtifactModel,
    SetupProbabilityPredictionModel, SetupOutcomeObservationModel,
)
from .policy import DEFAULT_POLICY
from .option_expression import ShadowOptionExpressionAdvisor
from .probability import HierarchicalSetupProbabilityEngine
from .repository import SetupIntelligenceRepository, utc_now


class SetupIntelligenceService:
    publication_name = "current_setup_intelligence_shadow"
    version = "M78-GOVERNED-SETUP-INTELLIGENCE-1.0"

    def __init__(self, session, policy=DEFAULT_POLICY):
        self.session = session
        self.policy = policy
        self.repo = SetupIntelligenceRepository(session)
        self.detector = GovernedSetupDetector(policy)
        self.probability = HierarchicalSetupProbabilityEngine(policy)
        self.ev = SetupExpectedValueEngine()
        self.option_expression = ShadowOptionExpressionAdvisor()

    def latest_stock_publication(self):
        return self.session.scalar(select(StockScannerPublicationModel).where(
            StockScannerPublicationModel.publication_name == "current_stock_intelligence",
            StockScannerPublicationModel.status.in_(("READY", "DEGRADED"))).order_by(desc(StockScannerPublicationModel.snapshot_timestamp)).limit(1))

    def capture(self, *, symbols: list[str] | None = None, max_candidates: int | None = None) -> dict:
        publication = self.latest_stock_publication()
        if publication is None:
            raise RuntimeError("No READY/DEGRADED current_stock_intelligence publication")
        query = select(StockScannerCandidateModel).where(StockScannerCandidateModel.scanner_run_id == publication.scanner_run_id)
        if symbols: query = query.where(StockScannerCandidateModel.symbol.in_([x.upper() for x in symbols]))
        query = query.order_by(desc(StockScannerCandidateModel.score), StockScannerCandidateModel.symbol)
        if max_candidates: query = query.limit(max_candidates)
        candidates = list(self.session.scalars(query))
        setup_count = 0; by_type: dict[str, int] = {}; transition_count = 0
        for candidate in candidates:
            previous = self.repo.latest_for_symbol(candidate.symbol, limit=10)
            prior_stage_by_type = {str(x.setup_type): str(x.stage) for x in previous}
            for setup in self.detector.detect(candidate, previous=previous):
                row = self.repo.save_snapshot(setup); setup_count += 1; by_type[setup.setup_type] = by_type.get(setup.setup_type, 0) + 1
                prev = prior_stage_by_type.get(setup.setup_type)
                if self.repo.save_transition(setup, prev, "deterministic governed setup lifecycle transition") is not None:
                    transition_count += 1
        pub = self.repo.publish(publication.scanner_run_id, setup_count, {"version": self.version,
            "candidate_count": len(candidates), "setup_counts": by_type, "transition_count": transition_count,
            "source_publication": "current_stock_intelligence", "source_publication_status": publication.status})
        self.session.commit()
        return {"status": pub.status, "publication_id": pub.publication_id, "source_scanner_run_id": publication.scanner_run_id,
                "candidate_count": len(candidates), "setup_count": setup_count, "setup_counts": by_type,
                "transition_count": transition_count, "authority_effect": False}

    def materialize_outcomes(self) -> dict:
        pairs = self.session.execute(select(SetupIntelligenceSnapshotModel, OutcomeProbabilityObservationModel).join(
            OutcomeProbabilityObservationModel, OutcomeProbabilityObservationModel.candidate_id == SetupIntelligenceSnapshotModel.candidate_id)).all()
        saved = 0
        for setup, outcome in pairs:
            self.repo.save_outcome(setup, outcome); saved += 1
        self.session.commit()
        readiness = self.probability.readiness(self.repo.outcomes())
        return {"status": readiness["status"], "materialized": saved, "readiness": readiness, "authority_effect": False}

    def train(self, *, model_version: str | None = None) -> dict:
        rows = self.repo.outcomes()
        version = model_version or f"M78-SETUP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        artifact, evaluation = self.probability.train(rows, version)
        model = self.repo.save_model(version, artifact, evaluation)
        self.repo.audit(model.model_id, "CHALLENGER_TRAINED", "SYSTEM", "M78 setup-specific challenger trained", evaluation)
        self.session.commit()
        return {"status": "CHALLENGER", "model_id": model.model_id, "model_version": model.model_version,
                "evaluation": evaluation, "authority_effect": False, "automatic_activation": False}

    def approve_shadow(self, model_id: str, *, actor: str, reason: str) -> dict:
        model = self.repo.model(model_id)
        if model is None: raise ValueError(f"Unknown M78 model {model_id}")
        if model.lifecycle_state != "CHALLENGER": raise ValueError(f"Model must be CHALLENGER, found {model.lifecycle_state}")
        model.lifecycle_state = "SHADOW_APPROVED"; model.approved_by = actor; model.approved_at = utc_now()
        self.repo.audit(model_id, "SHADOW_APPROVED", actor, reason, {"model_version": model.model_version})
        self.session.commit(); return {"status": model.lifecycle_state, "model_id": model_id, "authority_effect": False}

    def activate_shadow(self, model_id: str, *, actor: str, reason: str) -> dict:
        model = self.repo.model(model_id)
        if model is None: raise ValueError(f"Unknown M78 model {model_id}")
        if model.lifecycle_state != "SHADOW_APPROVED": raise ValueError(f"Model must be SHADOW_APPROVED, found {model.lifecycle_state}")
        for current in self.session.scalars(select(SetupProbabilityModelArtifactModel).where(SetupProbabilityModelArtifactModel.lifecycle_state == "SHADOW_ACTIVE")):
            current.lifecycle_state = "SHADOW_RETIRED"
        model.lifecycle_state = "SHADOW_ACTIVE"; model.activated_by = actor; model.activated_at = utc_now()
        self.repo.audit(model_id, "SHADOW_ACTIVATED", actor, reason, {"model_version": model.model_version, "authority_effect": False})
        self.session.commit(); return {"status": model.lifecycle_state, "model_id": model_id, "authority_effect": False}

    def predict_latest(self) -> dict:
        model = self.repo.active_shadow_model()
        if model is None: return {"status": "NO_ACTIVE_SHADOW_MODEL", "predictions": 0, "authority_effect": False}
        pub = self.session.scalar(select(SetupIntelligenceSnapshotModel.scanner_run_id).order_by(desc(SetupIntelligenceSnapshotModel.as_of)).limit(1))
        rows = list(self.session.scalars(select(SetupIntelligenceSnapshotModel).where(SetupIntelligenceSnapshotModel.scanner_run_id == pub))) if pub else []
        ready = insufficient = 0; ranked = []
        for setup in rows:
            probability = self.probability.predict(setup, model.artifact_json or {})
            risk = None
            if setup.entry_reference and setup.invalidation_level:
                risk = abs(float(setup.entry_reference) - float(setup.invalidation_level)) / max(abs(float(setup.entry_reference)), 1e-9) * 100.0
            ev = self.ev.assess(setup, probability, risk_pct=risk)
            self.repo.save_prediction(setup, model, probability, ev)
            if probability.status == "READY": ready += 1
            else: insufficient += 1
            expression = self.option_expression.advise(setup.setup_type, probability_status=probability.status,
                expected_holding_days=probability.expected_holding_days)
            ranked.append({"setup_id": setup.setup_id, "symbol": setup.symbol, "setup_type": setup.setup_type,
                "setup_stage": setup.stage, "setup_quality": setup.quality, "probability": asdict(probability),
                "expected_value": asdict(ev), "shadow_option_expression": expression})
        self.session.commit()
        ranked.sort(key=lambda x: (x["expected_value"].get("quality_adjusted_utility") is not None,
                                   x["expected_value"].get("quality_adjusted_utility") or -999), reverse=True)
        return {"status": "READY", "model_id": model.model_id, "predictions": len(rows), "ready": ready,
                "insufficient_evidence": insufficient, "ranking": ranked, "authority_effect": False}

    def prospective_evaluation(self, setup_type: str, model_id: str) -> dict:
        pairs = self.session.execute(
            select(SetupProbabilityPredictionModel, SetupOutcomeObservationModel)
            .join(SetupOutcomeObservationModel, SetupOutcomeObservationModel.setup_id == SetupProbabilityPredictionModel.setup_id)
            .where(SetupProbabilityPredictionModel.model_id == model_id, SetupOutcomeObservationModel.setup_type == setup_type,
                   SetupProbabilityPredictionModel.target_1_probability.is_not(None), SetupOutcomeObservationModel.target_1_before_stop.is_not(None))
            .order_by(SetupProbabilityPredictionModel.predicted_at)
        ).all()
        n=len(pairs)
        if not n:
            return {"status":"INSUFFICIENT_EVIDENCE","observations":0,"minimum_required":self.policy.minimum_prospective_observations}
        brier=sum((float(pred.target_1_probability)-int(out.target_1_before_stop))**2 for pred,out in pairs)/n
        wins=sum(int(out.target_1_before_stop) for _,out in pairs)
        ready=n>=self.policy.minimum_prospective_observations and wins>0 and wins<n
        passed=ready and brier<=self.policy.maximum_prospective_brier
        return {"status":"PASS" if passed else ("FAIL" if ready else "INSUFFICIENT_EVIDENCE"),
                "observations":n,"wins":wins,"losses":n-wins,"brier_score":round(brier,8),
                "maximum_brier":self.policy.maximum_prospective_brier,"minimum_required":self.policy.minimum_prospective_observations}

    def certify(self, setup_type: str, model_id: str, *, actor: str, reason: str) -> dict:
        # Certification is shadow-only; prospective evidence is computed from frozen predictions and later realized outcomes.
        readiness = self.probability.readiness([x for x in self.repo.outcomes() if str(x.setup_type) == setup_type])
        historical = "PASS" if readiness["status"] == "READY" else "INSUFFICIENT_EVIDENCE"
        prospective_eval = self.prospective_evaluation(setup_type, model_id)
        prospective = prospective_eval["status"]
        state = "CERTIFIED_SHADOW" if historical == "PASS" and prospective == "PASS" else ("FAIL" if prospective == "FAIL" else "INSUFFICIENT_EVIDENCE")
        row = SetupCertificationModel(certification_id=f"M78-CERT-{uuid4().hex.upper()}", setup_type=setup_type,
            model_id=model_id, state=state, historical_gate=historical, prospective_gate=prospective,
            evidence_json={"readiness": readiness, "prospective_evaluation": prospective_eval, "reason": reason, "production_promotion": False}, authority_effect=0,
            certified_by=actor if state == "CERTIFIED_SHADOW" else None, certified_at=utc_now() if state == "CERTIFIED_SHADOW" else None)
        self.session.add(row); self.repo.audit(row.certification_id, "CERTIFICATION_EVALUATED", actor, reason,
            {"state": state, "historical_gate": historical, "prospective_gate": prospective, "prospective_evaluation": prospective_eval})
        self.session.commit(); return {"status": state, "historical_gate": historical, "prospective_gate": prospective,
                                      "prospective_evaluation": prospective_eval, "authority_effect": False, "production_promotion": False}

    def status(self) -> dict:
        publication = self.session.execute(select(func.count()).select_from(SetupIntelligenceSnapshotModel)).scalar_one()
        outcomes = len(self.repo.outcomes()); models = list(self.session.scalars(select(SetupProbabilityModelArtifactModel).order_by(desc(SetupProbabilityModelArtifactModel.created_at))))
        readiness = self.probability.readiness(self.repo.outcomes())
        return {"status": "READY", "version": self.version, "setup_snapshots": int(publication or 0), "outcomes": outcomes,
            "readiness": readiness, "models": [{"model_id": x.model_id, "model_version": x.model_version, "state": x.lifecycle_state,
            "sample_size": x.sample_size} for x in models], "active_shadow_model": self.repo.active_shadow_model().model_id if self.repo.active_shadow_model() else None,
            "certifications": [{"setup_type": x.setup_type, "state": x.state, "historical_gate": x.historical_gate,
            "prospective_gate": x.prospective_gate} for x in self.repo.certification_status()],
            "governance": {"authority_effect": False, "automatic_promotion": False, "production_behavior_unchanged": True,
            "prospective_certification_required": True}}
