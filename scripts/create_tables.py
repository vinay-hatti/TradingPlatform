from trading_ai.database import Base, engine

# Import models so SQLAlchemy registers them
from trading_ai.market.models import PriceHistory  # noqa: F401

Base.metadata.create_all(bind=engine)

print("Database initialized successfully.")
