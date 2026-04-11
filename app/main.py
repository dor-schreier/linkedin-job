from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.pages import router as pages_router
from app.routes.scrape import router as scrape_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Job Finder", lifespan=lifespan)
app.include_router(health_router)
app.include_router(scrape_router)
app.include_router(jobs_router)
app.include_router(pages_router)
