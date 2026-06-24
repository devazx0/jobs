import sys
from app.database import Base, engine
from app.pipeline import run_daily_pipeline

if __name__ == "__main__":
    print("[Cron] Verifying database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[Cron] Database tables verified successfully.")
    except Exception as e:
        print(f"[Cron] Error verifying database tables: {e}", file=sys.stderr)
        sys.exit(1)

    print("[Cron] Starting daily job scraper and evaluator...")
    try:
        result = run_daily_pipeline()
        print(f"[Cron] Execution completed successfully.")
        print(f"[Cron] Result message: {result['message']}")
    except Exception as e:
        print(f"[Cron] Execution failed: {e}", file=sys.stderr)
        sys.exit(1)
