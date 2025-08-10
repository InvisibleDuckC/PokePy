from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "pokemon.db")
DEFAULT_DB_URL = os.environ.get("POKE_DB_URL", f"sqlite:///{os.path.abspath(DEFAULT_DB_PATH)}")

engine = create_engine(DEFAULT_DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

@contextmanager
def session_scope() -> Iterator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
