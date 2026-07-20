from dataclasses import dataclass

@dataclass(frozen=True)
class PatternDiscoveryPolicy:
    minimum_similarity_score: float = 0.35
    high_similarity_score: float = 0.75
    maximum_matches: int = 25
    minimum_cluster_size: int = 2
    symbol_weight: float = 0.20
    sector_weight: float = 0.15
    strategy_weight: float = 0.20
    tag_weight: float = 0.25
    outcome_weight: float = 0.10
    thesis_status_weight: float = 0.10

    def validate(self) -> None:
        fields=("minimum_similarity_score","high_similarity_score","symbol_weight","sector_weight","strategy_weight","tag_weight","outcome_weight","thesis_status_weight")
        for name in fields:
            value=float(getattr(self,name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.maximum_matches <= 0 or self.minimum_cluster_size <= 0:
            raise ValueError("maximum_matches and minimum_cluster_size must be positive.")
        total=sum(getattr(self,n) for n in ("symbol_weight","sector_weight","strategy_weight","tag_weight","outcome_weight","thesis_status_weight"))
        if abs(total-1.0)>1e-9:
            raise ValueError("Similarity weights must sum to 1.0.")
