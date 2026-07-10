from sqlalchemy.orm import sessionmaker
from trading_ai.database.engine import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_session():
    return SessionLocal()


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
