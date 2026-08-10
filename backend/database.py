"""SQLAlchemy engine, session factory and declarative base for StudyTrack.

Everything database-connection related lives here so the rest of the backend never
has to know where the database file is or how sessions are created.
"""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Resolve the SQLite file relative to the repository root rather than the current
# working directory, so the app always opens the same database no matter where
# uvicorn was launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'studytrack.db'}"

# check_same_thread=False is required because FastAPI serves requests from a
# threadpool, and SQLite would otherwise refuse a connection created on another thread.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores FOREIGN KEY constraints unless this pragma is switched on per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session.

    The session is opened before the route body runs and closed afterwards, even if
    the route raises -- that is what the `yield` inside the `try/finally` buys us.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
