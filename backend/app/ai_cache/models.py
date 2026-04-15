from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, String, Index

from app.database.base import Base


class AiCache(Base):
    __tablename__ = "ai_cache"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)

    # context
    state = Column(String(40), nullable=False, index=True)

    # the normalized user text we cached for
    prompt_key = Column(String(255), nullable=False, index=True)

    # what we returned to user
    answer = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_ai_cache_tenant_state_key", AiCache.tenant_id, AiCache.state, AiCache.prompt_key, unique=True)