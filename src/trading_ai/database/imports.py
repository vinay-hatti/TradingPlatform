"""
Central place to load all ORM models.

This prevents circular imports and ensures Alembic sees everything.
"""

from trading_ai.market.models import PriceHistory

__all__ = ["PriceHistory"]
