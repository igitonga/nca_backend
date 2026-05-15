from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base 

class MetricEvent(Base):
    __tablename__ = "metric_events"
    
    id = Column(Integer, primary_key=True, index=True)
    app_token_id = Column(Integer, ForeignKey("app_tokens.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    value = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    session_id = Column(String, nullable=False)
    device_id = Column(String, nullable=False)
    attributes = Column(JSON, nullable=True)  
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=True
    )
    updated_at = Column(
        DateTime(timezone=True), 
        onupdate=func.now(),
        nullable=True
    )
    
    app_token = relationship("AppToken", back_populates="metric_events")