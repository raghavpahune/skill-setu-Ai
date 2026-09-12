"""Multi-Horizon Future Skill Forecasting Engine (Phase 27).

Predicts skill demand trajectories across 6-month, 12-month, and 24-month horizons
by combining:
1. Historical & current job-posting velocity.
2. Direct first-party employer demand submissions.
3. Live industry signals & technology breakthroughs.
4. Graduate placement feedback.
"""
import logging
from typing import Any
from app.db import get_demo
from app.services.career_recommendation_engine import is_live_employer_demand

logger = logging.getLogger("skillsetu.forecast_engine")


def compute_multi_horizon_forecasts(is_demo: bool | None = None) -> list[dict[str, Any]]:
    """Compute 6m, 12m, 24m forecast trajectories and confidence for all skills."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        skills = get_demo("skills")
        jobs = get_demo("jobs")
        job_skills = get_demo("job_skills")
        employer_demands = get_demo("employer_demands")
        industry_signals = get_demo("industry_signals")
        stored_forecasts = {f.get("skill_id"): f for f in get_demo("skill_forecasts") if f.get("skill_id")}
    else:
        try:
            from app.repositories.supabase_repository import list_jobs, list_job_skills, list_skills, SupabaseRepositoryError
            skills = list_skills(limit=10000) or []
            jobs = list_jobs(limit=10000) or []
            job_ids = {j.get("id") for j in jobs if j.get("id")}
            repo_js = list_job_skills(job_ids=list(job_ids)) if job_ids else []
            job_skills = [js for js in (repo_js or []) if js.get("job_id") in job_ids]
        except SupabaseRepositoryError:
            raise
        except Exception as e:
            logger.warning("[ForecastEngine] Supabase unavailable for real forecast request: %s", e)
            skills = []
            jobs = []
            job_skills = []

        try:
            from app.repositories.supabase_repository import list_employer_demands
            employer_demands = list_employer_demands() or []
        except Exception as e:
            logger.warning("[ForecastEngine] Employer demands unavailable: %s", e)
            employer_demands = []

        try:
            from app.repositories.supabase_repository import list_industry_signals as list_industry_signals_repo
            industry_signals = list_industry_signals_repo() or []
        except Exception:
            industry_signals = []

        try:
            from app.repositories.supabase_repository import list_skill_forecasts, SupabaseRepositoryError
            raw_stored = list_skill_forecasts() or []
        except SupabaseRepositoryError:
            raise
        except Exception:
            raw_stored = []

        stored_forecasts = {}
        for f in raw_stored:
            sid = f.get("skill_id")
            if not sid:
                continue
            if sid not in stored_forecasts or f.get("confidence", 0) > stored_forecasts[sid].get("confidence", 0):
                stored_forecasts[sid] = f

    if not skills:
        return []

    # 1. Calculate Current Job Demand Velocity per skill
    total_jobs = max(1, len(jobs))
    skill_job_counts: dict[str, int] = {}
    for js in job_skills:
        sid = js.get("skill_id")
        if sid:
            skill_job_counts[sid] = skill_job_counts.get(sid, 0) + 1

    # 2. Calculate Employer Demand Pull (strictly live validated/approved records)
    employer_pull: dict[str, float] = {}
    for ed in employer_demands:
        if not is_live_employer_demand(ed):
            continue
        status = (ed.get("validation_status") or ed.get("status") or "").upper()
        if status not in ("VALIDATED", "APPROVED"):
            continue
        if ed.get("is_active") is False:
            continue
        demand_weight = {"HIGH": 3.0, "CRITICAL": 4.0, "MEDIUM": 1.5, "LOW": 0.5}.get(
            str(ed.get("hiring_demand", "")).upper(), 1.0
        )
        for req_skill in ed.get("required_skills", []) or ed.get("skills", []):
            s_name = req_skill.lower()
            employer_pull[s_name] = employer_pull.get(s_name, 0.0) + demand_weight

    # 3. Calculate Industry Signal Acceleration
    signal_impact: dict[str, dict[str, Any]] = {}
    for sig in industry_signals:
        if sig.get("is_active", True) and sig.get("validation_status") != "REJECTED":
            impact_factor = {"HIGH": 2.5, "CRITICAL": 3.5, "MEDIUM": 1.5, "LOW": 0.5}.get(
                str(sig.get("impact_level", "")).upper(), 1.5
            )
            for s_name in sig.get("skills", []) + sig.get("tools", []):
                sn_clean = s_name.lower().strip()
                if sn_clean not in signal_impact:
                    signal_impact[sn_clean] = {"score": 0.0, "drivers": [], "titles": []}
                signal_impact[sn_clean]["score"] += impact_factor
                driver = f"{sig.get('category', 'INDUSTRY')}: {sig.get('title')}"
                if driver not in signal_impact[sn_clean]["drivers"]:
                    signal_impact[sn_clean]["drivers"].append(driver)
                if sig.get("title") not in signal_impact[sn_clean]["titles"]:
                    signal_impact[sn_clean]["titles"].append(sig.get("title"))

    forecast_results = []

    for sk in skills:
        sid = sk.get("id")
        s_name = sk.get("name")
        if not sid or not s_name:
            continue
        s_name_lower = s_name.lower().strip()
        category = sk.get("category", "General")
        nsqf = sk.get("nsqf_level", 5)

        # Baseline demand score (0-100)
        job_count = skill_job_counts.get(sid, 0)
        job_pct = (job_count / total_jobs) * 100.0
        current_demand_score = min(100.0, round(job_pct * 2.2 + 20.0, 1))

        # Employer & Signal Boosts
        emp_score = employer_pull.get(s_name_lower, 0.0)
        sig_data = signal_impact.get(s_name_lower, {"score": 0.0, "drivers": [], "titles": []})
        sig_score = sig_data["score"]

        # Base trend heuristic from stored demo or signals
        stored = stored_forecasts.get(sid, {})
        base_confidence = stored.get("confidence", 80)
        base_growth = {"rising": 1.25, "stable": 1.05, "declining": 0.85}.get(
            stored.get("trend", "rising"), 1.15
        )

        # Apply multiplier based on real-time signals & employer demand
        growth_multiplier_6m = base_growth + (emp_score * 0.03) + (sig_score * 0.04)
        growth_multiplier_12m = base_growth * 1.15 + (emp_score * 0.06) + (sig_score * 0.08)
        growth_multiplier_24m = base_growth * 1.30 + (emp_score * 0.10) + (sig_score * 0.14)

        proj_6m = min(100.0, max(5.0, round(current_demand_score * growth_multiplier_6m, 1)))
        proj_12m = min(100.0, max(5.0, round(current_demand_score * growth_multiplier_12m, 1)))
        proj_24m = min(100.0, max(5.0, round(current_demand_score * growth_multiplier_24m, 1)))

        # Determine trend label
        if proj_24m > current_demand_score * 1.25:
            trend = "RISING"
        elif proj_24m < current_demand_score * 0.85:
            trend = "DECLINING"
        elif current_demand_score < 40 and proj_24m > 60:
            trend = "EMERGING"
        else:
            trend = "STABLE"

        # Determine Key Drivers
        drivers = sig_data["drivers"][:3]
        if not drivers:
            stored_drivers = stored.get("key_drivers")
            if stored_drivers:
                drivers = stored_drivers
            elif emp_score > 0 or job_count > 0:
                drivers = ["Employer demand expansion", "Regional industry hiring"]
            elif is_demo_mode:
                drivers = [
                    "Labour market digital transformation",
                    "Maharashtra industrial corridor expansion"
                ]
            else:
                drivers = ["Labour market baseline demand"]

        # Confidence calculation
        confidence = min(98, max(65, int(base_confidence + (2 if emp_score > 0 else 0) + (3 if sig_score > 0 else 0))))

        forecast_results.append({
            "skill_id": sid,
            "skill_name": s_name,
            "category": category,
            "nsqf_level": nsqf,
            "current_demand_score": current_demand_score,
            "projected_6m": proj_6m,
            "projected_12m": proj_12m,
            "projected_24m": proj_24m,
            "trend": trend,
            "growth_rate_pct": round(((proj_24m - current_demand_score) / max(1.0, current_demand_score)) * 100, 1),
            "confidence_score": confidence,
            "key_drivers": drivers,
            "related_signals": sig_data["titles"][:3],
            "horizon_breakdown": {
                "6_months": {"score": proj_6m, "demand_level": "CRITICAL" if proj_6m > 80 else ("HIGH" if proj_6m > 60 else "MEDIUM")},
                "12_months": {"score": proj_12m, "demand_level": "CRITICAL" if proj_12m > 85 else ("HIGH" if proj_12m > 65 else "MEDIUM")},
                "24_months": {"score": proj_24m, "demand_level": "CRITICAL" if proj_24m > 90 else ("HIGH" if proj_24m > 70 else "MEDIUM")},
            }
        })

    forecast_results.sort(key=lambda x: x["projected_24m"], reverse=True)
    return forecast_results


def get_skill_forecast_trajectory(skill_id: str, is_demo: bool | None = None) -> dict[str, Any] | None:
    """Retrieve detailed forecast trajectory for an individual skill."""
    all_fc = compute_multi_horizon_forecasts(is_demo=is_demo)
    for fc in all_fc:
        if fc["skill_id"] == skill_id or fc["skill_name"].lower() == skill_id.lower():
            return fc
    return None


def generate_future_skills_radar(is_demo: bool | None = None) -> dict[str, Any]:
    """Generate categorized radar clusters of emerging, high-growth, and mature skills."""
    all_fc = compute_multi_horizon_forecasts(is_demo=is_demo)

    rising_cluster = [f for f in all_fc if f["trend"] == "RISING"][:8]
    emerging_cluster = [f for f in all_fc if f["trend"] == "EMERGING"][:6]
    stable_cluster = [f for f in all_fc if f["trend"] == "STABLE"][:6]
    declining_cluster = [f for f in all_fc if f["trend"] == "DECLINING"][:4]

    # Aggregations
    top_domains: dict[str, list[dict]] = {}
    for f in all_fc:
        cat = f["category"]
        if cat not in top_domains:
            top_domains[cat] = []
        top_domains[cat].append(f)

    domain_growth = [
        {
            "domain": domain,
            "avg_growth_pct": round(sum(s["growth_rate_pct"] for s in skills) / max(1, len(skills)), 1),
            "skill_count": len(skills),
            "top_skill": max(skills, key=lambda s: s["projected_24m"])["skill_name"] if skills else "N/A"
        }
        for domain, skills in top_domains.items()
    ]
    domain_growth.sort(key=lambda x: x["avg_growth_pct"], reverse=True)

    return {
        "status": "success",
        "total_skills_forecasted": len(all_fc),
        "rising_skills": rising_cluster,
        "emerging_skills": emerging_cluster,
        "stable_skills": stable_cluster,
        "declining_skills": declining_cluster,
        "domain_growth_matrix": domain_growth,
    }


def persist_computed_forecasts(forecasts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Authoritatively persist multi-horizon forecast projections to Supabase repository.

    Translates computed multi-horizon projections into canonical 6m, 12m, 24m skill_forecasts
    records and upserts them through the Supabase repository, ensuring zero duplicate records.
    """
    if forecasts is None:
        forecasts = compute_multi_horizon_forecasts(is_demo=False)

    from app.repositories.supabase_repository import create_skill_forecast

    def _score_to_demand_level(score: float) -> str:
        if score >= 80.0:
            return "very_high"
        elif score >= 60.0:
            return "high"
        elif score >= 40.0:
            return "medium"
        return "low"

    def _normalize_trend(t: str) -> str:
        t_clean = str(t).lower().strip()
        if t_clean in ("rising", "emerging"):
            return "rising"
        elif t_clean in ("declining", "dropping"):
            return "declining"
        return "stable"

    persisted = []
    for fc in forecasts:
        sid = fc.get("skill_id")
        if not sid:
            continue
        current_dem = _score_to_demand_level(fc.get("current_demand_score", 50.0))
        trend_val = _normalize_trend(fc.get("trend", "stable"))
        conf_val = int(fc.get("confidence_score", 80))

        horizons = [
            ("6m", fc.get("projected_6m", 50.0)),
            ("12m", fc.get("projected_12m", 50.0)),
            ("24m", fc.get("projected_24m", 50.0)),
        ]

        for period, proj_score in horizons:
            fut_dem = _score_to_demand_level(proj_score)
            record = {
                "skill_id": sid,
                "period": period,
                "current_demand": current_dem,
                "future_demand": fut_dem,
                "trend": trend_val,
                "confidence": conf_val,
            }
            try:
                saved = create_skill_forecast(record)
                persisted.append(saved)
            except Exception as e:
                logger.warning("[ForecastEngine] Skipped skill forecast persistence for %s (%s): %s", sid, period, e)

    return persisted
