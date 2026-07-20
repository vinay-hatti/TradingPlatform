from __future__ import annotations
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field

class ScannerQuery(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    signal: Literal["CALL","PUT","ALL"] = "ALL"
    min_score: float = 0
    max_results: int = Field(default=100, ge=1, le=1000)

class ScannerResult(BaseModel):
    symbol: str
    as_of: date | None = None
    signal: str
    call_score: float = 0
    put_score: float = 0
    confidence: float = 0
    market_regime: str = "UNKNOWN"
    expected_move_1d: float = 0
    atr14: float = 0
    rsi14: float = 0
    source: str

class FeatureImportanceRow(BaseModel):
    feature: str
    importance: float
    rank: int
    direction: Literal["POSITIVE","NEGATIVE","MIXED","UNKNOWN"] = "UNKNOWN"

class WalkForwardRun(BaseModel):
    run_id: str
    symbol: str | None = None
    train_start: date | None = None
    train_end: date | None = None
    test_start: date | None = None
    test_end: date | None = None
    net_pnl: float = 0
    win_rate: float = 0
    sharpe_ratio: float = 0
    max_drawdown: float = 0
    trades: int = 0
    source_file: str

class ReplayRequest(BaseModel):
    symbol: str
    start: date
    end: date
    speed: Literal["STEP","FAST"] = "STEP"

class ReplayFrame(BaseModel):
    sequence: int
    timestamp: date
    symbol: str
    close: float
    rsi14: float | None = None
    atr14: float | None = None
    call_score: float | None = None
    put_score: float | None = None
    signal: str | None = None
    market_regime: str | None = None
