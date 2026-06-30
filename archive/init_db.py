from src.database.database import engine
from src.market.models import Base

print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Done!")
