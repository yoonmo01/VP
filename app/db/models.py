from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, ForeignKey, TIMESTAMP, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import TIMESTAMP
from app.db.base import Base

# 1) 피싱범
class PhishingOffender(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

# 2) 피해자
class Victim(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    knowledge: Mapped[dict] = mapped_column(JSON, default=dict)
    traits: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

# 3) 관리자 케이스(간소화: 피싱여부 + 근거만)
class AdminCase(Base):
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario: Mapped[dict] = mapped_column(JSON, default=dict)
    phishing: Mapped[bool | None] = mapped_column()
    evidence: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="running")   # ✅ running/completed/aborted
    defense_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ✅ 방어 횟수
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)  # ✅ 완료 시각

# 4) 대화 로그
class ConversationLog(Base):
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admincase.id"), index=True)
    offender_id: Mapped[int] = mapped_column(ForeignKey("phishingoffender.id"))
    victim_id: Mapped[int] = mapped_column(ForeignKey("victim.id"))
    turn_index: Mapped[int] = mapped_column(Integer)   # 0..N
    role: Mapped[str] = mapped_column(String(20))      # offender/victim
    content: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    case = relationship("AdminCase")

    __table_args__ = (
        Index("ix_conv_case_turn", "case_id", "turn_index"),
        UniqueConstraint("case_id", "turn_index", name="uq_case_turn"),
    )

# # ✅ 정렬 인덱스 + 유니크 제약(중복 턴 방지)
# Index("ix_conv_case_turn", ConversationLog.case_id, ConversationLog.turn_index)
# UniqueConstraint(ConversationLog.case_id, ConversationLog.turn_index, name="uq_case_turn")


