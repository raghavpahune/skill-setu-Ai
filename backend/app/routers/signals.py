"""Industry Signals & Technology Intelligence API.

Provides:
- GET /api/industry/signals (Public: filters by category, industry, skill, tool, freshness, search)
- GET /api/industry/signals/{id} (Public: detail of approved, active signal)
- GET /api/signals & /api/signals/{id} (Backward compatibility aliases)
"""
import asyncio
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from app.core.data_mode import is_explicit_demo_mode
from app.db import get_demo
from app.ingestion.industry_intelligence import calculate_freshness, STATUS_APPROVED
from app.repositories.supabase_repository import (
    list_industry_signals as list_industry_signals_repo,
    get_industry_signal as get_industry_signal_repo,
    SupabaseRepositoryError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_skills_map(is_demo: bool = False) -> dict[str, str]:
    if is_demo:
        return {s["id"]: s["name"] for s in get_demo("skills")}
    try:
        from app.repositories.supabase_repository import list_skills
        return {s["id"]: s.get("name", s["id"]) for s in (list_skills() or []) if "id" in s}
    except Exception:
        return {}


def _normalize_signal_output(sig: dict[str, Any], skills_map: dict[str, str]) -> dict[str, Any]:
    published_at = sig.get("published_at") or (f"{sig['signal_date']}T00:00:00Z" if sig.get("signal_date") else "2026-01-01T00:00:00Z")
    is_active = True if sig.get("is_active") is None else bool(sig.get("is_active"))
    val_status = sig.get("validation_status") or STATUS_APPROVED
    freshness = sig.get("freshness") or calculate_freshness(published_at, is_active, val_status)

    skills = sig.get("skills", [])
    if not skills and "affected_skills" in sig:
        skills = [skills_map.get(sid, sid) for sid in sig.get("affected_skills", [])]

    affected_legacy = [
        {"skill_id": s, "skill_name": skills_map.get(s, s)}
        for s in sig.get("affected_skills", [])
    ] or [{"skill_id": s, "skill_name": s} for s in skills]

    return {
        "id": sig.get("id"),
        "title": sig.get("title"),
        "description": sig.get("description") or sig.get("summary") or "",
        "summary": sig.get("summary") or sig.get("description") or "",
        "category": sig.get("category", "INDUSTRY_DEMAND"),
        "industry": sig.get("industry") or sig.get("technology") or "Cross-Sector Tech",
        "technology": sig.get("technology") or sig.get("industry") or "Emerging Technology",
        "skills": skills,
        "tools": sig.get("tools", []),
        "source_name": sig.get("source_name") or sig.get("source") or "Industry Analysis",
        "source": sig.get("source") or sig.get("source_name") or "Industry Analysis",
        "source_url": sig.get("source_url") or "https://data.gov.in",
        "source_type": sig.get("source_type") or "INDUSTRY_ANNOUNCEMENT",
        "published_at": published_at,
        "collected_at": sig.get("collected_at") or published_at,
        "updated_at": sig.get("updated_at") or published_at,
        "signal_date": published_at[:10] if published_at else "2026-01-01",
        "impact_level": sig.get("impact_level", "high"),
        "validation_status": val_status,
        "is_demo": bool(sig.get("is_demo") or sig.get("source_label") == "DEMO_SYNTHETIC" or sig.get("source_type") == "DEMO_SYNTHETIC" or sig.get("source") == "DEMO_SYNTHETIC"),
        "data_provenance": sig.get("data_provenance") or ("DEMO_SYNTHETIC" if (sig.get("is_demo") or sig.get("source_label") == "DEMO_SYNTHETIC" or sig.get("source_type") == "DEMO_SYNTHETIC" or sig.get("source") == "DEMO_SYNTHETIC") else "UNVERIFIED_EXTERNAL_SOURCE"),
        "freshness": freshness,
        "affected_skills": affected_legacy,
        "is_ai_processed": sig.get("is_ai_processed", False),
        "ai_metadata": sig.get("ai_metadata"),
        "is_active": is_active,
    }


@router.get("/industry/signals")
async def list_industry_signals(
    category: str | None = Query(None, description="Category filter (e.g. EMERGING_SKILL, INDUSTRY_DEMAND)"),
    industry: str | None = Query(None, description="Industry filter (e.g. IT, Automotive, EV)"),
    skill: str | None = Query(None, description="Skill name filter"),
    tool: str | None = Query(None, description="Tool name filter"),
    freshness: str | None = Query(None, description="Freshness grade: NEW, RECENT, OLDER, EXPIRED"),
    source: str | None = Query(None, description="Source name filter"),
    search: str | None = Query(None, description="Search query across title, description, skills, tools"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    if is_explicit_demo_mode(is_demo):
        raw_signals = get_demo("industry_signals")
    else:
        try:
            repo_signals = list_industry_signals_repo() or []
            raw_signals = [s for s in repo_signals if not s.get("is_demo") and s.get("source") != "DEMO_SYNTHETIC" and s.get("source_label") != "DEMO_SYNTHETIC" and s.get("source_type") != "DEMO_SYNTHETIC" and s.get("data_provenance") != "DEMO_SYNTHETIC"]
        except SupabaseRepositoryError as e:
            logger.exception("[Signals] Failed listing industry signals from Supabase: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failure listing industry signals.",
            )
    skills_map = _get_skills_map(is_demo=is_explicit_demo_mode(is_demo))

    normalized = [_normalize_signal_output(s, skills_map) for s in raw_signals]

    # Filter only approved and active for public view
    results = [s for s in normalized if s.get("is_active") is True and s.get("validation_status") == STATUS_APPROVED]

    if category and category.lower() != "all":
        results = [s for s in results if s.get("category", "").lower() == category.lower()]

    if industry and industry.lower() != "all":
        results = [s for s in results if industry.lower() in s.get("industry", "").lower() or industry.lower() in s.get("technology", "").lower()]

    if skill and skill.lower() != "all":
        results = [s for s in results if any(skill.lower() in sk.lower() for sk in s.get("skills", []))]

    if tool and tool.lower() != "all":
        results = [s for s in results if any(tool.lower() in t.lower() for t in s.get("tools", []))]

    if freshness and freshness.lower() != "all":
        results = [s for s in results if s.get("freshness", "").lower() == freshness.lower()]

    if source and source.lower() != "all":
        results = [s for s in results if source.lower() in s.get("source_name", "").lower() or source.lower() in s.get("source", "").lower()]

    if search and search.strip():
        q = search.strip().lower()
        results = [
            s for s in results
            if q in s.get("title", "").lower()
            or q in s.get("description", "").lower()
            or any(q in sk.lower() for sk in s.get("skills", []))
            or any(q in tl.lower() for tl in s.get("tools", []))
            or q in s.get("industry", "").lower()
        ]

    # Sort by published_at descending
    results.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    return {
        "status": "success",
        "total": len(results),
        "signals": results[offset : offset + limit],
    }


@router.get("/industry/signals/{signal_id}")
async def get_industry_signal(
    signal_id: str,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Retrieve detailed metadata for an approved active industry signal."""
    if is_explicit_demo_mode(is_demo):
        matched = next((s for s in get_demo("industry_signals") if s.get("id") == signal_id), None)
    else:
        try:
            matched = get_industry_signal_repo(signal_id)
            if matched and (
                matched.get("is_demo") is True
                or matched.get("source") == "DEMO_SYNTHETIC"
                or matched.get("source_label") == "DEMO_SYNTHETIC"
                or matched.get("source_type") == "DEMO_SYNTHETIC"
                or matched.get("data_provenance") == "DEMO_SYNTHETIC"
            ):
                matched = None
        except SupabaseRepositoryError as e:
            logger.exception("[Signals] Failed fetching industry signal '%s' from Supabase: %s", signal_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failure fetching industry signal.",
            )
    if not matched:
        raise HTTPException(status_code=404, detail=f"Industry signal '{signal_id}' not found.")

    skills_map = _get_skills_map(is_demo=is_explicit_demo_mode(is_demo))
    normalized = _normalize_signal_output(matched, skills_map)
    if not normalized.get("is_active") or normalized.get("validation_status") != STATUS_APPROVED:
        raise HTTPException(status_code=404, detail=f"Industry signal '{signal_id}' is not active or approved.")

    return {"status": "success", "signal": normalized}


@router.get("/signals")
async def legacy_list_signals(
    is_demo: bool | None = Query(None),
):
    if is_explicit_demo_mode(is_demo):
        raw_signals = get_demo("industry_signals")
    else:
        try:
            repo_signals = list_industry_signals_repo() or []
            raw_signals = [s for s in repo_signals if not s.get("is_demo") and s.get("source") != "DEMO_SYNTHETIC" and s.get("source_label") != "DEMO_SYNTHETIC" and s.get("source_type") != "DEMO_SYNTHETIC" and s.get("data_provenance") != "DEMO_SYNTHETIC"]
        except SupabaseRepositoryError as e:
            logger.exception("[Signals] Failed listing signals: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failure listing signals.",
            )
    skills_map = _get_skills_map(is_demo=is_explicit_demo_mode(is_demo))
    results = [_normalize_signal_output(s, skills_map) for s in raw_signals if s.get("is_active", True)]
    results.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return results


@router.get("/signals/{signal_id}")
async def legacy_get_signal(
    signal_id: str,
    is_demo: bool | None = Query(None, description="Explicit demo/real mode selector"),
):
    """Legacy backward-compatible detail endpoint."""
    if is_explicit_demo_mode(is_demo):
        matched = next((s for s in get_demo("industry_signals") if s.get("id") == signal_id), None)
    else:
        try:
            matched = get_industry_signal_repo(signal_id)
            if matched and (matched.get("is_demo") is True or matched.get("source") == "DEMO_SYNTHETIC"):
                matched = None
        except SupabaseRepositoryError as e:
            logger.exception("[Signals] Failed fetching signal '%s': %s", signal_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failure fetching signal.",
            )
    if not matched:
        return {"error": "not found"}
    skills_map = _get_skills_map(is_demo=is_explicit_demo_mode(is_demo))
    return _normalize_signal_output(matched, skills_map)
