"""Recommendation Service — generates curriculum recommendations from gaps + signals + forecasts."""
from app.db import get_demo
from app.services.gap_engine import compute_gaps


def get_curriculum_recommendations(is_demo: bool | None = None) -> list[dict]:
    """Generate curriculum recommendations based on skill gaps, forecasts, and industry signals."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    gaps = compute_gaps(is_demo=is_demo_mode)
    if is_demo_mode:
        forecasts = get_demo("skill_forecasts")
        signals = get_demo("industry_signals")
        skills_map = {s["id"]: s for s in get_demo("skills")}
    else:
        from app.repositories.supabase_repository import list_skill_forecasts, list_skills
        try:
            forecasts = list_skill_forecasts() or []
        except Exception:
            forecasts = []
        try:
            from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo
            signals = list_industry_signals_repo() or []
        except Exception:
            signals = []
        try:
            repo_skills = list_skills(limit=None) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
        except Exception:
            skills_map = {}

    # Build forecast lookup (best period per skill)
    fc_map = {}
    for f in forecasts:
        sid = f["skill_id"]
        if sid not in fc_map or f.get("confidence", 0) > fc_map[sid].get("confidence", 0):
            fc_map[sid] = f

    # Build signal lookup
    sig_skills = {}
    for sig in signals:
        for sid in sig.get("affected_skills", []):
            if sid not in sig_skills:
                sig_skills[sid] = []
            sig_skills[sid].append(sig["title"])

    recommendations = []
    for gap in gaps:
        if gap["priority"] not in ("CRITICAL", "HIGH"):
            continue

        sid = gap["skill_id"]
        skill = skills_map.get(sid, {})
        fc = fc_map.get(sid, {})
        related_signals = sig_skills.get(sid, [])

        reason_parts = []
        if gap["demand_pct"] > 20:
            reason_parts.append(f"job demand is {gap['demand_pct']}% of postings")
        if gap["coverage_pct"] < 40:
            reason_parts.append(f"curriculum coverage is only {gap['coverage_pct']}%")
        if fc.get("trend") == "rising":
            reason_parts.append(f"future demand trend is rising ({fc.get('confidence', 'N/A')}% confidence)")
        if related_signals:
            reason_parts.append(f"industry signal: {related_signals[0]}")

        reason = "Recommended because " + ", ".join(reason_parts) + "." if reason_parts else "Based on skill gap analysis."

        recommendations.append({
            "skill_id": sid,
            "skill_name": gap["skill_name"],
            "recommendation": f"Add or strengthen {gap['skill_name']} training module",
            "reason": reason,
            "gap_pct": gap["gap_pct"],
            "priority": gap["priority"],
            "future_demand": fc.get("future_demand", "unknown"),
            "trend": fc.get("trend", "unknown"),
            "confidence": fc.get("confidence", 0),
            "related_signals": related_signals[:2],
        })

    recommendations.sort(key=lambda x: x["gap_pct"], reverse=True)
    return recommendations
