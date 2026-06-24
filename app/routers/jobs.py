from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job
from app.pipeline import get_jobs, evaluate_jobs, upsert_jobs
from app.schemas import JobResponse, JobListResponse, JobUpdate, ScrapeResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    applied: Optional[bool] = Query(None),
    min_score: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if applied is not None:
        query = query.filter(Job.applied == applied)
    if min_score is not None:
        query = query.filter(Job.score >= min_score)
    if q:
        query = query.filter(
            Job.title.ilike(f"%{q}%") | Job.company.ilike(f"%{q}%")
        )
    total = query.count()
    jobs = query.order_by(Job.score.desc()).offset(skip).limit(limit).all()
    return JobListResponse(total=total, jobs=jobs)


@router.get("/unapplied", response_model=JobListResponse)
def unapplied_jobs(
    min_score: Optional[int] = Query(65),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.applied == False)
    if min_score is not None:
        query = query.filter(Job.score >= min_score)
    total = query.count()
    jobs = query.order_by(Job.score.desc()).offset(skip).limit(limit).all()
    return JobListResponse(total=total, jobs=jobs)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, body: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.applied is not None:
        job.applied = body.applied
        job.applied_at = datetime.now(timezone.utc) if body.applied else None
    if body.notes is not None:
        job.notes = body.notes
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_and_evaluate(db: Session = Depends(get_db)):
    raw_jobs = get_jobs()
    if not raw_jobs:
        return ScrapeResponse(jobs_found=0, new_added=0, message="No jobs found.")

    scored = evaluate_jobs(raw_jobs)
    new_added = upsert_jobs(db, scored)
    return ScrapeResponse(
        jobs_found=len(scored),
        new_added=new_added,
        message=f"Found {len(scored)} jobs, added {new_added} new.",
    )
