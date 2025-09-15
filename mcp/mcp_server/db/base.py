# base.py
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
import os

class Base(DeclarativeBase): ...

DB_URL = os.getenv("MCP_DATABASE_URL", "sqlite:///./mcp_sim.db")
_engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

def init_db():
    from .models import Conversation, TurnLog
    Base.metadata.create_all(_engine)
