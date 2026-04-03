from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from services.kanban.dispatcher import Dispatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIBRARIAN_URL = os.getenv("LIBRARIAN_URL", "http://localhost:8001")
WORKER_URL = os.getenv("WORKER_URL", "http://localhost:8004")

dispatcher = Dispatcher(librarian_url=LIBRARIAN_URL, worker_url=WORKER_URL)
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events using lifespan context manager"""
    # Startup
    scheduler.add_job(
        poll_and_dispatch_job,
        trigger="interval",
        seconds=30,  # Poll every 30 seconds
        id="poll_and_dispatch",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Kanban dispatcher started (30s polling)")
    yield
    # Shutdown
    scheduler.shutdown()


def poll_and_dispatch_job():
    """Background job: poll Librarian and dispatch tasks"""
    try:
        dispatched = dispatcher.poll_and_dispatch()
        if dispatched > 0:
            logger.info(f"Dispatched {dispatched} tasks")
    except Exception as e:
        logger.error(f"Dispatch error: {e}")


app = FastAPI(title="Sea Qwens Kanban", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "healthy", "scheduler_running": scheduler.running}


@app.post("/dispatch/now")
def dispatch_now():
    """Trigger immediate dispatch (for testing)"""
    dispatched = dispatcher.poll_and_dispatch()
    return {"dispatched": dispatched}


@app.get("/status")
def get_status():
    """Get dispatcher status"""
    return {
        "scheduler_running": scheduler.running,
        "polling_interval": "30s"
    }
