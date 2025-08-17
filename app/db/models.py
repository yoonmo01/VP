from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, ForeignKey, TIMESTAMP, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from uuid import uuid4
from datetime import datetime, timezone
from app.db.base import Base

# 1) 피싱범
class PhishingOffender(Base):
    __tablename__ = "phishingoffender"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)   # ← JSONB
    source: Mapped[dict | None] = mapped_column(JSONB, default=dict)            # 사례 출처 JSON
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

# 2) 피해자
class Victim(Base):
    __tablename__ = "victim"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)       # ← JSONB
    knowledge: Mapped[dict] = mapped_column(JSONB, default=dict)  # ← JSONB
    traits: Mapped[dict] = mapped_column(JSONB, default=dict)     # ← JSONB
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

# 3) 관리자 케이스
class AdminCase(Base):
    __tablename__ = "admincase"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario: Mapped[dict] = mapped_column(JSONB, default=dict)   # ← JSONB
    phishing: Mapped[bool | None] = mapped_column()
    evidence: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="running")   # running/completed/aborted
    defense_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

# 4) 대화 로그 (하이브리드: TEXT + JSONB)
class ConversationLog(Base):
    __tablename__ = "conversationlog"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admincase.id"), index=True)
    offender_id: Mapped[int] = mapped_column(ForeignKey("phishingoffender.id"))
    victim_id: Mapped[int] = mapped_column(ForeignKey("victim.id"))
    turn_index: Mapped[int] = mapped_column(Integer)                   # 정렬 키 유지
    role: Mapped[str] = mapped_column(String(20))                      # offender/victim
    content: Mapped[str] = mapped_column(Text)                         # 기존 유지(점진 전환)
    label: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # ← 신설 JSONB
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("AdminCase")

    __table_args__ = (
        Index("ix_conv_case_turn", "case_id", "turn_index"),
        UniqueConstraint("case_id", "turn_index", name="uq_case_turn"),
        # GIN 인덱스는 Alembic에서 추가 (모델에선 안 잡힘)
    )
