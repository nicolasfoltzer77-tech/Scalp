# storage/db.py
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def make_sqlite_engine(path: str = "var/trading.db"):
    url = f"sqlite:///{path}"
    engine = create_engine(url, echo=False, future=True)
    return engine

def make_session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()
