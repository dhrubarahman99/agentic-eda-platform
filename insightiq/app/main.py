# InsightIQ — Agentic AI Analytics API

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.database import init_db
init_db()

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.upload import router as upload_router
from app.api.analysis import router as analysis_router
from app.api.query import router as query_router
from app.api.llm import router as llm_router
from app.api.dashboard import router as dashboard_router
from app.api.export import router as export_router
from app.api.sessions import router as sessions_router
from app.api.feedback import router as feedback_router
from app.api.admin import router as admin_router

app = FastAPI(
    title="InsightIQ",
    description="Agentic AI Analytics System for non-technical users.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

@app.get("/", tags=["Root"])
async def root() -> dict:
    return {"service": "InsightIQ", "docs": "/docs"}