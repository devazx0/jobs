from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import cron, jobs
from app.schemas import HealthResponse


def run_scheduled_pipeline():
    from app.pipeline import run_daily_pipeline
    result = run_daily_pipeline()
    print(f"[Scheduler] Daily pipeline result: {result['message']}")


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    scheduler.add_job(
        run_scheduled_pipeline,
        "cron",
        hour=settings.daily_cron_hour,
        timezone=settings.daily_cron_timezone,
        id="daily_job_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Scheduler] Daily pipeline scheduled for hour={settings.daily_cron_hour} {settings.daily_cron_timezone}")

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI Job Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(cron.router)


@app.get("/health", response_model=HealthResponse)
def health():
    from sqlalchemy import text
    from app.database import SessionLocal
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "error"
    return HealthResponse(status="ok", database=db_status, app_env=settings.app_env)
