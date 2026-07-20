from typing import Any
from pydantic import BaseModel, Field

class ResearchScannerRequest(BaseModel):
    universe: str = "core_options"
    maximum_results: int = Field(20, ge=1, le=200)
    minimum_average_volume: int = Field(500000, ge=0)
    minimum_option_volume: int = Field(100, ge=0)
    minimum_open_interest: int = Field(100, ge=0)
    maximum_spread_pct: float = Field(0.20, ge=0)
    minimum_iv_rank: float = Field(0.0, ge=0, le=100)
    minimum_atr_pct: float = Field(0.5, ge=0)
    required_signals: list[str] = Field(default_factory=lambda: ["CALL", "PUT"])

class ResearchScannerCandidate(BaseModel):
    rank: int
    symbol: str
    composite_score: float
    signal: str
    regime: str
    price: float
    option_volume: int
    open_interest: int
    spread_pct: float
    iv_rank: float
    iv_percentile: float
    decision_confidence: float
    expected_return: float
    risk_score: float
    reward_risk_ratio: float
    institutional: dict[str, Any] = Field(default_factory=dict)

class ResearchScannerResponse(BaseModel):
    scan_id: str
    universe: str
    requested_count: int
    candidate_count: int
    rejected_count: int
    skipped_symbols: list[str]
    results: list[ResearchScannerCandidate]
    report_path: str
    warnings: list[str] = Field(default_factory=list)
