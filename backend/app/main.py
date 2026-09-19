"""FastAPI application for SkillSetu backend."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure repository root is in sys.path so 'ai' module is importable across all runtimes
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and settings.demo_auth_enabled:
        raise RuntimeError(
            "FATAL: Demo authentication cannot be enabled in production mode (DEMO_AUTH_ENABLED=true)."
        )
    if settings.is_production and not (settings.jwt_secret_key and settings.jwt_secret_key.strip()):
        raise RuntimeError(
            "FATAL: Production JWT secret is mandatory. Set JWT_SECRET_KEY in production environment variables."
        )

    # Startup: initialize database layer (demo data + Supabase overlay)
    from app.db import init_db
    init_db()

    # Startup: start background data synchronization scheduler
    from app.ingestion.scheduler import scheduler
    scheduler.start()

    yield

    # Shutdown: stop background scheduler gracefully
    await scheduler.stop()


app = FastAPI(
    title="SkillSetu API",
    description="AI-Powered Labour-Market Intelligence & Curriculum-Alignment Platform",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
if settings.cors_origins:
    for o in settings.cors_origins.split(","):
        cleaned = o.strip()
        if cleaned and cleaned != "*":
            _allowed_origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import (
    auth, skills, jobs, gaps, courses, signals, forecast,
    districts, student, copilot, employer, schemes, opportunities, sync,
    simulator, admin, gov_opportunities, institute, curriculum, profile,
    placements,
)

app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(profile.router, prefix="/api", tags=["Profiles"])

app.include_router(skills.router, prefix="/api", tags=["Skills"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(gaps.router, prefix="/api", tags=["Skill Gaps"])
app.include_router(courses.router, prefix="/api", tags=["Courses"])
app.include_router(curriculum.router, prefix="/api", tags=["Curriculum Modernization"])
app.include_router(placements.router, prefix="/api", tags=["Placement Outcomes & Workforce Feedback"])
app.include_router(institute.router, prefix="/api", tags=["Institute"])
app.include_router(signals.router, prefix="/api", tags=["Industry Signals"])
app.include_router(forecast.router, prefix="/api", tags=["Forecast"])
app.include_router(districts.router, prefix="/api", tags=["Districts"])
app.include_router(student.router, prefix="/api", tags=["Student"])
app.include_router(copilot.router, prefix="/api", tags=["AI Copilot"])
app.include_router(employer.router, prefix="/api", tags=["Employer"])
app.include_router(schemes.router, prefix="/api", tags=["Schemes"])
app.include_router(opportunities.router, prefix="/api", tags=["Opportunities"])
app.include_router(sync.router, prefix="/api", tags=["Data Ingestion & Sync"])
app.include_router(simulator.router, prefix="/api", tags=["Policy Simulator"])
app.include_router(admin.router, prefix="/api", tags=["Admin Data Management"])
app.include_router(gov_opportunities.router, prefix="/api", tags=["Government Opportunities"])


@app.get("/")
async def root():
    """Simple service endpoint for Render health probes and browser checks."""
    return {
        "status": "ok",
        "service": "SkillSetu API",
        "health": "/api/health",
    }


@app.get("/health")
@app.get("/api/health")
async def health():
    import os
    from app.db import _cache, _find_data_dir, is_supabase_connected
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or settings.gemini_api_key
    total_records = sum(len(v) for v in _cache.values() if isinstance(v, list))
    jobs = _cache.get("jobs", [])
    districts = sorted(list(set(j.get("district") for j in jobs if j.get("district"))))
    return {
        "status": "ok",
        "demo_mode": settings.use_demo_data,
        "ai_available": bool(key and key.strip()),
        "records_loaded": total_records,
        "tables_loaded": len(_cache),
        "data_dir": str(_find_data_dir()),
        "jobs_count": len(jobs),
        "districts_count": len(districts),
        "districts": districts,
        "supabase_connected": is_supabase_connected(),
    }


@app.get("/api/health/ai")
async def health_ai():
    """Safe diagnostic endpoint for AI provider status without exposing secrets."""
    from ai.gemini_provider import GeminiProvider
    provider = GeminiProvider()
    probe_result = await provider.diagnose()
    return probe_result
