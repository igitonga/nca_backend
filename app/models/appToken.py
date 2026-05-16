from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class AppToken(Base):
    __tablename__ = "app_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String, nullable=False)
    label = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )

    metric_events = relationship(
        "MetricEvent",
        back_populates="app_token",
        cascade="all, delete-orphan",
    )
