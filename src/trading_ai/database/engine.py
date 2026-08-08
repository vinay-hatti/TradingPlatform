from sqlalchemy import create_engine

from trading_ai.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_use_lifo=True,
    echo=False,
)
