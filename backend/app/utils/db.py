import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# load environment variables from .env if present
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session, closing it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_db_query(fn):
    """Utility that opens a session, runs the provided callback, and returns its result."""
    with SessionLocal() as session:
        return fn(session)


# create tables on import; safe in development but may be skipped in production
Base.metadata.create_all(bind=engine)
