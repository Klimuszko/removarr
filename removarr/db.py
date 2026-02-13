from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

class Base(DeclarativeBase):
    pass

def _ensure_sqlite_dir(db_url: str) -> None:
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
        directory = os.path.dirname(path)
        if directory and directory != ".":
            os.makedirs(directory, exist_ok=True)

def make_engine(db_url: str):
    _ensure_sqlite_dir(db_url)
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, future=True, pool_pre_ping=True, connect_args=connect_args)

def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
