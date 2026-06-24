from fastapi import APIRouter

from app.pipeline import run_daily_pipeline
from app.schemas import DailyCronResponse

router = APIRouter(prefix="/cron", tags=["cron"])


@router.post("/daily", response_model=DailyCronResponse)
def daily_job():
    result = run_daily_pipeline()
    return DailyCronResponse(**result)
