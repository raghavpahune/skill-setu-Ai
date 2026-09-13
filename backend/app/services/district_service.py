"""District Service — aggregated district-level training plans and platform metrics."""
from collections import Counter
import datetime
import math
from typing import Any
from app.db import get_demo
from app.services.career_recommendation_engine import is_live_employer_demand
from app.services.gap_engine import compute_gaps
from app.services.curriculum_engine import audit_all_courses, EQUIPMENT_CATALOG, TRAINER_UPGRADE_CATALOG


def get_all_districts(is_demo: bool | None = None) -> list[dict]:
    from app.core.data_mode import is_explicit_demo_mode
    if is_explicit_demo_mode(is_demo):
        jobs = get_demo("jobs")
        courses = get_demo("courses")
    else:
        try:
            from app.repositories.supabase_repository import list_jobs, list_courses
            jobs = list_jobs(limit=10000) or []
            courses = list_courses() or []
        except Exception:
            jobs = []
            courses = []
    
    job_counts = Counter(j["district"] for j in jobs if j.get("district"))
    course_counts = Counter(c["district"] for c in courses if c.get("district"))
    
    all_names = sorted(set(job_counts.keys()) | set(course_counts.keys()))
    
    return [
        {
            "name": name,
            "job_count": job_counts.get(name, 0),
            "course_count": course_counts.get(name, 0),
        }
        for name in sorted(all_names, key=lambda n: job_counts.get(n, 0), reverse=True)
    ]


def get_district_plan(district: str, is_demo: bool | None = None) -> dict[str, Any]:
    """Generate a comprehensive training plan for a district covering all §13 requirements."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        jobs = get_demo("jobs")
        courses = get_demo("courses")
        skills_map = {s["id"]: s for s in get_demo("skills")}
        placements = get_demo("placements")
        employer_demands = get_demo("employer_demands")
    else:
        try:
            from app.repositories.supabase_repository import list_jobs
            jobs = list_jobs(limit=10000) or []
        except Exception:
            jobs = []

        try:
            from app.repositories.supabase_repository import list_courses
            courses = list_courses() or []
        except Exception:
            courses = []

        try:
            from app.repositories.supabase_repository import list_skills
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
        except Exception:
            skills_map = {}

        try:
            from app.repositories.supabase_repository import list_placements
            placements = sorted(
                list_placements() or [],
                key=lambda r: r.get("year") or 0,
            )
        except Exception:
            placements = []

        try:
            from app.repositories.supabase_repository import list_employer_demands
            employer_demands = list_employer_demands() or []
        except Exception:
            employer_demands = []

    audited_courses_all = audit_all_courses(is_demo=is_demo)

    # Normalize district string
    d_clean = district.strip().lower()

    # 1. Filter jobs and courses to district
    district_jobs = [j for j in jobs if j.get("district", "").strip().lower() == d_clean]
    district_courses = [c for c in courses if c.get("district", "").strip().lower() == d_clean]
    district_job_ids = {j["id"] for j in district_jobs}

    if is_demo_mode:
        job_skills = get_demo("job_skills")
    else:
        try:
            from app.repositories.supabase_repository import list_job_skills
            job_skills = list_job_skills(job_ids=list(district_job_ids)) if district_job_ids else []
        except Exception:
            job_skills = []

    # 2. Top 5 Demanded Roles (§13)
    role_counts = Counter(j["title"] for j in district_jobs if j.get("title"))

    skills_by_name = {s["name"].lower(): s["id"] for s in skills_map.values()}
    district_js = [js for js in job_skills if js.get("job_id") in district_job_ids]
    skill_counts = Counter(js["skill_id"] for js in district_js if js.get("skill_id"))

    for ed in employer_demands:
        if not is_live_employer_demand(ed):
            continue
        status = (ed.get("validation_status") or ed.get("status") or "").upper()
        if status not in ("VALIDATED", "APPROVED"):
            continue
        ed_dist = (ed.get("district") or "").strip().lower()
        if ed_dist == d_clean or not ed_dist:
            role = ed.get("job_role") or ed.get("role_title") or ed.get("target_role") or ed.get("job_title") or ed.get("title")
            openings = ed.get("openings_count") or ed.get("positions_count") or ed.get("openings") or 5
            if role:
                role_counts[role] += openings
            for sk in ed.get("required_skills") or ed.get("skills") or []:
                sk_name = sk if isinstance(sk, str) else sk.get("name", "")
                sid = sk if sk in skills_map else skills_by_name.get(str(sk_name).lower())
                if sid:
                    skill_counts[sid] += openings

    top_roles = [{"role": r, "count": c} for r, c in role_counts.most_common(5)]
    if not top_roles and is_demo is not False:
        top_roles = [
            {"role": "Industrial Automation Specialist", "count": max(8, len(district_jobs))},
            {"role": "Solar Power Systems Technician", "count": max(6, int(len(district_jobs) * 0.7))},
            {"role": "Precision CNC Machinist", "count": max(4, int(len(district_jobs) * 0.5))},
        ]

    # 3. Top Skills Demanded in District (§13)
    top_skills = [
        {
            "skill_id": sid,
            "skill_name": skills_map.get(sid, {}).get("name", "Specialized Skill"),
            "category": skills_map.get(sid, {}).get("category", "General Technical"),
            "demand_count": cnt,
        }
        for sid, cnt in skill_counts.most_common(10)
    ]
    if not top_skills and is_demo is not False:
        top_skills = [
            {"skill_id": "sk-024", "skill_name": "PLC Programming", "category": "Manufacturing", "demand_count": 14},
            {"skill_id": "sk-035", "skill_name": "Solar PV Systems", "category": "Green Energy", "demand_count": 12},
            {"skill_id": "sk-018", "skill_name": "EV Battery Maintenance", "category": "Electric Vehicles", "demand_count": 10},
        ]

    # 4. District Skill Gaps (§13 & §10)
    gaps = compute_gaps(district=district, is_demo=is_demo)[:10]

    # 5. Local Registered Courses & Institutional Capacity (§13)
    placement_map = {p["course_id"]: p for p in placements if p.get("course_id")}
    local_courses = []
    for c in district_courses:
        p = placement_map.get(c["id"])
        has_placement = bool(p)
        if has_placement:
            sc = p.get("student_count") or (c.get("enrolment_count") or 60)
            pc = p.get("placed_count", 0)
            placement_rate = round((pc / max(1, sc)) * 100) if sc else 0
        else:
            placement_rate = 0 if is_demo_mode else None
        local_courses.append({
            "id": c["id"],
            "name": c.get("name") or c.get("title", ""),
            "institute": c.get("institute", f"Government ITI, {district}"),
            "enrolment": c.get("enrolment_count") or 0,
            "placement_rate": placement_rate,
            "placement_data_available": has_placement,
        })

    # 6. Industry Sector Clusters (§13)
    industry_counts = Counter(j["industry"] for j in district_jobs if j.get("industry"))
    industries = [{"industry": k, "count": v} for k, v in industry_counts.most_common()]
    if not industries and is_demo_mode:
        industries = [
            {"industry": "Manufacturing & Precision Engineering", "count": max(12, len(district_jobs))},
            {"industry": "AgriTech & Renewable Energy", "count": max(8, int(len(district_jobs) * 0.6))},
            {"industry": "Automotive Services & Logistics", "count": max(6, int(len(district_jobs) * 0.4))},
        ]

    total_enrolment = sum((c.get("enrolment_count") or 0) for c in district_courses)
    if not total_enrolment and is_demo_mode:
        total_enrolment = max(120, len(district_jobs) * 4)

    # 7. Courses Needing Review / Obsolescence Flags in District (§13 & §11)
    district_audited = [
        c for c in audited_courses_all
        if c.get("district", "").strip().lower() == d_clean
    ]
    courses_needing_review = [
        {
            "course_id": ac.get("course_id", ""),
            "name": ac.get("course_name") or ac.get("name", "Vocational Course"),
            "institute": ac.get("institute", ""),
            "health_score": ac.get("health_score", 0),
            "modernity_score": ac.get("modernity_score", 0),
            "placement_rate": ac.get("placement_rate", 0),
            "obsolescence_risk": ac.get("obsolescence_risk", "MODERATE"),
            "oversupply_status": ac.get("oversupply_status", "BALANCED"),
            "rationale": ac.get("rationale", "Placement rate below 50% with low industry demand."),
        }
        for ac in district_audited
        if ac.get("obsolescence_risk") in ("CRITICAL_OBSOLETE", "HIGH_RISK") or "OVERSUPPLY" in ac.get("oversupply_status", "")
    ]


    # 8. Required Training Seats Target (§13)
    total_seat_deficit = sum(
        max(30, int((g["gap_pct"] / 100) * 120))
        for g in gaps[:5]
    ) if gaps else (180 if is_demo_mode else 0)

    # 9. Required Equipment & Procurement Budget Allocation (§13)
    required_equipment = []
    total_equipment_budget_inr = 0
    gap_categories = {g.get("category", "") for g in gaps}
    if any("ai" in c.lower() or "data" in c.lower() for c in gap_categories):
        for item in EQUIPMENT_CATALOG.get("Artificial Intelligence", []):
            cost = item["units"] * item["unit_cost_inr"]
            total_equipment_budget_inr += cost
            required_equipment.append({**item, "total_cost_inr": cost, "domain": "Artificial Intelligence"})
    if any("ev" in c.lower() or "automotive" in c.lower() for c in gap_categories):
        for item in EQUIPMENT_CATALOG.get("Electric Vehicles", []):
            cost = item["units"] * item["unit_cost_inr"]
            total_equipment_budget_inr += cost
            required_equipment.append({**item, "total_cost_inr": cost, "domain": "Electric Vehicles"})
    if any("robot" in c.lower() or "manufactur" in c.lower() for c in gap_categories):
        for item in EQUIPMENT_CATALOG.get("Robotics & Automation", []):
            cost = item["units"] * item["unit_cost_inr"]
            total_equipment_budget_inr += cost
            required_equipment.append({**item, "total_cost_inr": cost, "domain": "Robotics & Automation"})
    if not required_equipment:
        for item in EQUIPMENT_CATALOG.get("General Technical", []):
            cost = item["units"] * item["unit_cost_inr"]
            total_equipment_budget_inr += cost
            required_equipment.append({**item, "total_cost_inr": cost, "domain": "General Technical Labs"})

    # 10. Required Trainers / Certified Instructors (§13)
    required_trainers_count = max(2, math.ceil(total_seat_deficit / 25)) if total_seat_deficit > 0 else 0
    trainer_programs = []
    if any("ai" in c.lower() for c in gap_categories):
        trainer_programs.extend(TRAINER_UPGRADE_CATALOG.get("Artificial Intelligence", []))
    if any("ev" in c.lower() for c in gap_categories):
        trainer_programs.extend(TRAINER_UPGRADE_CATALOG.get("Electric Vehicles", []))
    if not trainer_programs and (is_demo_mode or gaps):
        trainer_programs.extend(TRAINER_UPGRADE_CATALOG.get("General Technical", []))

    # 11. Nearby Accredited Training Institutes (§13)
    nearby_institutes = []
    for c in district_courses:
        inst_name = c.get("institute")
        if inst_name and inst_name not in [ni["name"] for ni in nearby_institutes]:
            nearby_institutes.append({
                "name": inst_name,
                "district": district,
                "type": "Direct ITI / Polytechnic",
                "active_courses_count": sum(1 for dc in district_courses if dc.get("institute") == inst_name),
            })
    if not nearby_institutes:
        nearby_institutes = [
            {"name": f"Government ITI, {district}", "district": district, "type": "Vocational Training Hub", "active_courses_count": 4 if is_demo_mode else 0},
            {"name": f"District Polytechnic Institute, {district}", "district": district, "type": "Technical Training Institute", "active_courses_count": 3 if is_demo_mode else 0},
        ]

    # 12. Recommended Modernized Courses (§13)
    recommended_courses = []
    for g in gaps[:4]:
        recommended_courses.append({
            "trade_name": f"Advanced {g['skill_name']} & Applied Systems",
            "category": g.get("category", "Emerging Tech"),
            "target_enrolment_seats": max(40, int((g["gap_pct"] / 100) * 100)),
            "associated_skill": g["skill_name"],
            "target_placement_rate_pct": min(95, 75 + int(g["gap_pct"] * 0.2)),
            "urgency": g.get("priority", "HIGH"),
        })

    # 13. Expected Impact Metrics (§13)
    avg_gap_before = round(sum(g["gap_pct"] for g in gaps) / max(1, len(gaps)), 1) if gaps else (35.0 if is_demo_mode else 0.0)
    projected_gap_after = min(avg_gap_before, max(0.0, round(avg_gap_before * 0.45, 1))) if avg_gap_before > 0 else 0.0
    expected_impact = {
        "projected_placement_lift_pct": 18.5 if (total_seat_deficit > 0 or is_demo_mode) else 0.0,
        "projected_skill_deficit_reduction_pct": round(((avg_gap_before - projected_gap_after) / max(1.0, avg_gap_before)) * 100, 1) if avg_gap_before > 0 else 0.0,
        "target_placed_students": int(total_seat_deficit * 0.85),
        "total_budget_estimate_inr": total_equipment_budget_inr + (required_trainers_count * 150000),
    }

    return {
        "district": district,
        "total_jobs": len(district_jobs) if not is_demo_mode else (len(district_jobs) or 38),
        "total_courses": len(district_courses),
        "total_enrolment": total_enrolment,
        "top_roles": top_roles,
        "top_demanded_roles": top_roles,
        "top_skills": top_skills,
        "top_demanded_skills": top_skills,
        "skill_gaps": gaps,
        "local_courses": local_courses,
        "industry_demand": industries,
        "recommended_courses": recommended_courses,
        "courses_needing_review": courses_needing_review,
        "required_training_seats": total_seat_deficit,
        "required_equipment": required_equipment,
        "total_equipment_budget_inr": total_equipment_budget_inr,
        "required_trainers_count": required_trainers_count,
        "trainer_programs": trainer_programs,
        "nearby_institutes": nearby_institutes,
        "expected_impact": expected_impact,
    }


def get_platform_metrics_summary(is_demo: bool | None = None) -> dict[str, Any]:
    """Compute the 7 platform-level success metrics specified in PROJECT_SPEC Section 33."""
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        jobs = get_demo("jobs")
        courses = get_demo("courses")
        skills = get_demo("skills")
        placements = get_demo("placements")
        employer_feedback = get_demo("employer_feedback")
    else:
        try:
            from app.repositories.supabase_repository import list_jobs
            jobs = list_jobs(limit=10000) or []
        except Exception:
            jobs = []
        try:
            from app.repositories.supabase_repository import list_courses
            courses = list_courses() or []
        except Exception:
            courses = []
        try:
            from app.repositories.supabase_repository import list_skills
            skills = list_skills(limit=10000) or []
        except Exception:
            skills = []
        try:
            from app.repositories.supabase_repository import list_placements
            placements = sorted(
                list_placements() or [],
                key=lambda r: r.get("year") or 0,
            )
        except Exception:
            placements = []
        try:
            from app.repositories.supabase_repository import list_employer_feedback
            employer_feedback = list_employer_feedback() or []
        except Exception:
            employer_feedback = []

    audited_courses = audit_all_courses(is_demo=is_demo)
    gaps = compute_gaps(is_demo=is_demo)

    # 1. State-wide Placement Rate
    total_students = sum(p.get("student_count", 0) for p in placements)
    total_placed = sum(p.get("placed_count", 0) for p in placements)
    placement_rate = round((total_placed / max(1, total_students)) * 100, 1) if total_students else (78.4 if is_demo_mode else 0.0)

    # 2. Net Skill Mismatch Score (Average Skill Gap Index 0-100)
    skill_mismatch_score = round(sum(g.get("gap_pct", 0) for g in gaps) / max(1, len(gaps)), 1) if gaps else (32.5 if is_demo_mode else 0.0)

    # 3. Employer Validation / Approval Rate (%)
    total_feedback = len(employer_feedback)
    confirmed_or_valid = sum(
        1 for ef in employer_feedback
        if str(ef.get("status", "")).lower() in ("confirmed", "validated", "approved")
    )
    employer_approval_rate = round((confirmed_or_valid / max(1, total_feedback)) * 100, 1) if total_feedback else (87.5 if is_demo_mode else 0.0)

    avg_curriculum_update_time_months = None
    if is_demo_mode:
        avg_curriculum_update_time_months = 3.8
    elif courses:
        diffs = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for c in courses:
            ts_raw = c.get("updated_at") or c.get("last_updated") or c.get("created_at")
            if ts_raw:
                try:
                    if isinstance(ts_raw, str):
                        ts = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    elif isinstance(ts_raw, (datetime.datetime, datetime.date)):
                        ts = ts_raw if isinstance(ts_raw, datetime.datetime) else datetime.datetime.combine(ts_raw, datetime.time.min, tzinfo=datetime.timezone.utc)
                    else:
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    diff_months = max(0.0, (now.timestamp() - ts.timestamp()) / (86400 * 30.4375))
                    diffs.append(diff_months)
                except Exception:
                    pass
        if diffs:
            avg_curriculum_update_time_months = round(sum(diffs) / len(diffs), 1)

    # 5. Training Capacity Deficit (Total missing seats in critical/high gap skills)
    training_capacity_deficit_seats = sum(
        max(40, int((g.get("gap_pct", 0) / 100) * 120))
        for g in gaps
        if g.get("priority") in ("CRITICAL", "HIGH")
    )

    # 6. Equipment & Trainer Gap Count
    equipment_trainer_gaps = sum(
        1 for c in audited_courses
        if c.get("obsolescence_risk") in ("CRITICAL_OBSOLETE", "HIGH_RISK") or c.get("total_equipment_budget_inr", 0) > 0
    )

    # 7. Student Recommendation Engagement Rate (%)
    student_engagement_rate = 86.2 if is_demo_mode else 0.0

    return {
        "status": "success",
        "placement_rate_pct": placement_rate,
        "skill_mismatch_score": skill_mismatch_score,
        "employer_approval_rate_pct": employer_approval_rate,
        "avg_curriculum_update_time_months": avg_curriculum_update_time_months,
        "training_capacity_deficit_seats": training_capacity_deficit_seats,
        "equipment_trainer_gap_count": equipment_trainer_gaps,
        "student_engagement_rate_pct": student_engagement_rate,
        "total_jobs_indexed": len(jobs),
        "total_skills_taxonomy": len(skills),
        "total_courses_audited": len(courses),
    }

