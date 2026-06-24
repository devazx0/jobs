from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    job_url: str
    description: str
    job_type: str
    score: int
    tag: str
    reasoning: str
    applied: bool
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    scraped_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    total: int
    jobs: list[JobResponse]


class JobUpdate(BaseModel):
    applied: Optional[bool] = None
    notes: Optional[str] = None


class ScrapeResponse(BaseModel):
    jobs_found: int
    new_added: int
    message: str


class DailyCronResponse(BaseModel):
    jobs_found: int
    new_added: int
    qualified: int
    email_sent: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    app_env: str
