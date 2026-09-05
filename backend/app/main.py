from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Case
from app.seed import seed_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Ensure DB file lives under backend/
    backend_dir = Path(__file__).resolve().parent.parent
    import os

    os.chdir(backend_dir)
    init_db()
    db = SessionLocal()
    try:
        if db.query(Case).count() == 0:
            seed_database(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title="RecoverAI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "RecoverAI",
        "tagline": "Detect → Diagnose → Decide → Act → Recover → Audit",
        "docs": "/docs",
    }
