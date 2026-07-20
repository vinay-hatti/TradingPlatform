from dataclasses import dataclass
@dataclass(frozen=True)
class OutcomeAttributionPolicy:
    minimum_data_completeness: float=.80
    minimum_decision_quality_score: float=.60
    minimum_thesis_confirmation_score: float=.70
    minimum_partial_confirmation_score: float=.40
    def validate(self):
        for n in ("minimum_data_completeness","minimum_decision_quality_score","minimum_thesis_confirmation_score","minimum_partial_confirmation_score"):
            v=float(getattr(self,n))
            if not 0<=v<=1: raise ValueError(f"{n} must be between 0 and 1")
