from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False)
    job_url = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    job_type = Column(String, default="")
    score = Column(Integer, default=0)
    tag = Column(String, default="")
    reasoning = Column(Text, default="")
    company_brief = Column(Text, default="", nullable=True)
    applied = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
