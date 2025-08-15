from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.sync_dsn, echo=settings.SYNC_ECHO)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)