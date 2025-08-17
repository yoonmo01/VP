# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from app.core.config import settings

# engine = create_engine(settings.sync_dsn, echo=settings.SYNC_ECHO)
# SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.sqlalchemy_url, echo=settings.SYNC_ECHO, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()