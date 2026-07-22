from __future__ import annotations
try:
    from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
    from sqlalchemy.orm import Mapped, mapped_column
    from trading_ai.database.models import Base
except Exception:  # metadata remains optional for file-only workflows
    Base = object

if Base is not object:
    class PositionMonitoringAssessmentModel(Base):
        __tablename__ = "position_monitoring_assessments"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        assessment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
        position_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
        portfolio_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
        symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
        decision: Mapped[str] = mapped_column(String(32), nullable=False)
        urgency: Mapped[str] = mapped_column(String(32), nullable=False)
        return_pct: Mapped[float] = mapped_column(Float, nullable=False)
        payload: Mapped[dict] = mapped_column(JSON, nullable=False)
        generated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    class PositionExitInstructionModel(Base):
        __tablename__ = "position_exit_instructions"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        instruction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
        assessment_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
        position_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
        action: Mapped[str] = mapped_column(String(32), nullable=False)
        quantity: Mapped[int] = mapped_column(Integer, nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        payload: Mapped[dict] = mapped_column(JSON, nullable=False)
        created_at: Mapped[str] = mapped_column(String(64), nullable=False)
