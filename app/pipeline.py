import json
import os
from datetime import datetime, timezone

from google import genai
from google.genai import types
import resend
from jobspy import scrape_jobs
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Job

import jobspy.model as _jm
_orig_from_string = _jm.Country.from_string.__func__
@classmethod
def _patched_from_string(cls, country_str):
    try:
        return _orig_from_string(cls, country_str)
    except ValueError:
        country_str = country_str.strip().lower()
        fallback = {"kenya": "south africa"}
        if country_str in fallback:
            return _orig_from_string(cls, fallback[country_str])
        raise
_jm.Country.from_string = _patched_from_string

JOB_TITLES = ["Backend Engineer", "AI Engineer", "Software Engineer"]
LOCATIONS = [
    ("Remote", True),
    ("Nigeria", False),
    ("United States", False),
    ("United Kingdom", False),
    ("Netherlands", False),
    ("Germany", False),
    ("Kenya", False),
    ("South Africa", False),
]
SENDER_IDENTITY = "AI Agent <onboarding@resend.dev>"
SCORE_THRESHOLD = 65


def get_jobs():
    print("Scraping jobs...")
    all_jobs = []
    seen_urls = set()
    for title in JOB_TITLES:
        for location, is_remote in LOCATIONS:
            try:
                jobs_df = scrape_jobs(
                    site_name=["linkedin"],
                    search_term=title,
                    location=location,
                    results_wanted=10,
                    is_remote=is_remote,
                )
                if not jobs_df.empty:
                    for _, row in jobs_df.iterrows():
                        url = row.get("job_url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_jobs.append({
                                "title": row.get("title", ""),
                                "company": row.get("company", ""),
                                "job_url": url,
                                "description": row.get("description", ""),
                                "job_type": row.get("job_type", ""),
                            })
            except Exception as e:
                print(f"[Scraper] Error scraping '{title}' in '{location}' (is_remote={is_remote}): {e}")
    return all_jobs


def evaluate_jobs(jobs):
    if not jobs:
        return []
    print(f"Evaluating {len(jobs)} jobs with Gemini Flash...")
    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = f"""
    You are an expert technical recruiter and career advisor.
    My Profile:
    - I am a Backend & AI Engineer.
    - My core stack: Node.js, NestJS, Prisma, TypeORM, PostgreSQL.
    - Infrastructure/DevOps: Docker, WSL2, Git, Railway, Vercel, DigitalOcean.
    - AI/Data: Building LLM Agents, Recommendation Systems (Collaborative Filtering, SVD, KNN).
    - Goal: Looking for remote Full-Time roles OR Freelance/Contract gigs.

    Review the following job listings. For each job:
    1. Check if the job type is strictly Full-Time, Contract, or Freelance. If it is unpaid, an internship, or strictly requires legacy enterprise tech, score it 0.
    2. Score the job from 0 to 100 based on how well it aligns with my modern backend (NestJS/Postgres) and AI engineering skills.
    3. Tag it with one of: "Highly Aligned", "Good Match", "Worth a Shot", "Skip".
    4. Write a 1-sentence reasoning for your score.
    5. Write a 1-sentence brief about the company (what they do, their industry).

    Return a JSON array of objects with the following keys: "title", "company", "job_url", "score", "tag", "reasoning", "company_brief".

    Jobs Data:
    {json.dumps(jobs)}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    evaluated_jobs = json.loads(response.text)
    return sorted(evaluated_jobs, key=lambda x: x["score"], reverse=True)


def upsert_jobs(db: Session, evaluated_jobs: list[dict]) -> int:
    new_added = 0
    for j in evaluated_jobs:
        existing = db.query(Job).filter(Job.job_url == j["job_url"]).first()
        if existing:
            existing.score = j.get("score", existing.score)
            existing.tag = j.get("tag", existing.tag)
            existing.reasoning = j.get("reasoning", existing.reasoning)
            existing.company_brief = j.get("company_brief", existing.company_brief)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            job = Job(
                title=j.get("title", ""),
                company=j.get("company", ""),
                job_url=j.get("job_url", ""),
                description="",
                job_type="",
                score=j.get("score", 0),
                tag=j.get("tag", ""),
                reasoning=j.get("reasoning", ""),
                company_brief=j.get("company_brief", ""),
            )
            db.add(job)
            new_added += 1
    db.commit()
    return new_added


def send_email(jobs: list[Job]):
    print("Sending email via Resend...")
    if not jobs:
        print("No qualified jobs to email.")
        return False

    resend.api_key = settings.resend_api_key

    html_content = "<h2>Your Curated Job Matches</h2>"
    for job in jobs:
        color = "green" if job.score >= 80 else "orange"
        html_content += f"""
        <div style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; font-family: sans-serif;">
            <h3 style="margin: 0;"><a href="{job.job_url}" style="color: #0056b3; text-decoration: none;">{job.title} @ {job.company}</a></h3>
            <p style="margin: 5px 0;">
                <strong style="color: {color};">Score: {job.score}/100</strong> |
                <span style="background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{job.tag}</span>
            </p>
            <p style="margin: 2px 0; color: #666; font-size: 13px;">{job.company_brief}</p>
            <p style="margin: 5px 0; color: #444; font-size: 14px;"><em>{job.reasoning}</em></p>
        </div>
        """

    try:
        r = resend.Emails.send(
            {
                "from": SENDER_IDENTITY,
                "to": [settings.email_receiver],
                "subject": "Daily AI Job Matches: Backend & AI Engineering",
                "html": html_content,
            }
        )
        print(f"Email sent successfully! ID: {r['id']}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def run_daily_pipeline() -> dict:
    raw_jobs = get_jobs()
    if not raw_jobs:
        return {"jobs_found": 0, "new_added": 0, "qualified": 0, "email_sent": False,
                "message": "No jobs found during scrape."}

    scored = evaluate_jobs(raw_jobs)

    db = SessionLocal()
    try:
        new_added = upsert_jobs(db, scored)

        qualified = (
            db.query(Job)
            .filter(Job.score >= SCORE_THRESHOLD, Job.applied == False)
            .order_by(Job.score.desc())
            .all()
        )

        email_sent = send_email(qualified) if qualified else False

        return {
            "jobs_found": len(scored),
            "new_added": new_added,
            "qualified": len(qualified),
            "email_sent": email_sent,
            "message": f"Found {len(scored)} jobs, added {new_added} new, {len(qualified)} qualified. Email {'sent' if email_sent else 'not sent'}.",
        }
    finally:
        db.close()
