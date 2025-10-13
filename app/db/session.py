from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# ✅ 강제로 DATABASE_URL 사용
DATABASE_URL = "postgresql+psycopg://vpuser:2400@127.0.0.1:5432/voicephish"

engine = create_engine(settings.sqlalchemy_url,
                       echo=settings.SYNC_ECHO,
                       pool_pre_ping=True,
                       connect_args={
        "options": "-c search_path=public"
    })

# ✅ 추가: 연결 시마다 스키마 확인
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def try_get_db():
    """DB 세션을 시도하되 실패하면 None을 반환한다."""
    try:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    except Exception:
        # DB 미설정/연결 실패 시 None
        yield None
