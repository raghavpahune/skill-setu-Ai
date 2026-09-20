import logging
import math
from typing import Any
from app.core.data_mode import is_explicit_demo_mode
from app.db import _cache, init_db
from app.services.curriculum_engine import TRAINER_UPGRADE_CATALOG

logger = logging.getLogger(__name__)

NSQF_STUDENT_TRAINER_RATIO_NORM = 20


def _get_trainers(institute_id: str | None = None, district: str | None = None, trade: str | None = None, is_demo: bool | None = None) -> list[dict[str, Any]]:
    if not _cache:
        init_db()
    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        trainers = _cache.get("institution_trainers", [])
    else:
        try:
            from app.repositories.supabase_repository import list_institution_trainers
            trainers = list_institution_trainers(institute_id=institute_id, district=district, trade=trade, is_demo=is_demo, limit=1000) or []
        except Exception:
            trainers = [t for t in _cache.get("institution_trainers", []) if is_demo is None or t.get("is_demo") == is_demo]

    filtered = trainers
    if institute_id:
        filtered = [t for t in filtered if t.get("institute_id", "").lower() == institute_id.strip().lower()]
    if district:
        filtered = [t for t in filtered if district.strip().lower() in (t.get("district") or "").lower()]
    if trade:
        filtered = [t for t in filtered if trade.strip().lower() in (t.get("primary_trade") or "").lower()]
    if is_demo is not None:
        filtered = [t for t in filtered if t.get("is_demo") == is_demo]
    return filtered


def _get_nominations(institute_id: str | None = None, district: str | None = None, status: str | None = None, is_demo: bool | None = None) -> list[dict[str, Any]]:
    if not _cache:
        init_db()
    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        noms = _cache.get("faculty_upskilling_nominations", [])
    else:
        try:
            from app.repositories.supabase_repository import list_faculty_nominations
            noms = list_faculty_nominations(institute_id=institute_id, district=district, status=status, is_demo=is_demo, limit=1000) or []
        except Exception:
            noms = [n for n in _cache.get("faculty_upskilling_nominations", []) if is_demo is None or n.get("is_demo") == is_demo]

    filtered = noms
    if institute_id:
        filtered = [n for n in filtered if n.get("institute_id", "").lower() == institute_id.strip().lower()]
    if district:
        filtered = [n for n in filtered if district.strip().lower() in (n.get("district") or "").lower()]
    if status:
        filtered = [n for n in filtered if (n.get("status") or "").upper() == status.strip().upper()]
    if is_demo is not None:
        filtered = [n for n in filtered if n.get("is_demo") == is_demo]
    return filtered


def list_institution_trainers_service(
    institute_id: str | None = None,
    district: str | None = None,
    trade: str | None = None,
    status: str | None = None,
    is_demo: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if not _cache:
        init_db()
    is_demo_mode = is_explicit_demo_mode(is_demo)
    trainers = None
    if not is_demo_mode:
        try:
            from app.repositories.supabase_repository import list_institution_trainers
            trainers = list_institution_trainers(
                institute_id=institute_id,
                district=district,
                trade=trade,
                is_demo=is_demo,
                limit=limit,
                offset=offset,
            )
        except Exception:
            trainers = None

    if trainers is None:
        cached = _cache.get("institution_trainers", [])
        filtered = cached
        if institute_id:
            filtered = [t for t in filtered if t.get("institute_id", "").lower() == institute_id.strip().lower()]
        if district:
            filtered = [t for t in filtered if district.strip().lower() in (t.get("district") or "").lower()]
        if trade:
            filtered = [t for t in filtered if trade.strip().lower() in (t.get("primary_trade") or "").lower()]
        if is_demo is not None:
            filtered = [t for t in filtered if t.get("is_demo") == is_demo]
        if status:
            filtered = [t for t in filtered if (t.get("status") or "").upper() == status.strip().upper()]
        trainers = filtered[offset: offset + limit]
    elif status:
        trainers = [t for t in trainers if (t.get("status") or "").upper() == status.strip().upper()]

    return trainers


def list_faculty_nominations_service(
    institute_id: str | None = None,
    district: str | None = None,
    status: str | None = None,
    is_demo: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if not _cache:
        init_db()
    is_demo_mode = is_explicit_demo_mode(is_demo)
    noms = None
    if not is_demo_mode:
        try:
            from app.repositories.supabase_repository import list_faculty_nominations
            noms = list_faculty_nominations(
                institute_id=institute_id,
                district=district,
                status=status,
                is_demo=is_demo,
                limit=limit,
                offset=offset,
            )
        except Exception:
            noms = None

    if noms is None:
        cached = _cache.get("faculty_upskilling_nominations", [])
        filtered = cached
        if institute_id:
            filtered = [n for n in filtered if n.get("institute_id", "").lower() == institute_id.strip().lower()]
        if district:
            filtered = [n for n in filtered if district.strip().lower() in (n.get("district") or "").lower()]
        if status:
            filtered = [n for n in filtered if (n.get("status") or "").upper() == status.strip().upper()]
        if is_demo is not None:
            filtered = [n for n in filtered if n.get("is_demo") == is_demo]
        noms = filtered[offset: offset + limit]

    return noms


def compute_course_trainer_capacity(
    course: dict[str, Any],
    trainers: list[dict[str, Any]],
) -> dict[str, Any]:
    cid = course.get("id") or ""
    cname = course.get("name") or "Vocational Program"
    enrolment = course.get("enrolment_capacity") or course.get("enrolment_count") or 60
    required_trainers = max(1, math.ceil(enrolment / NSQF_STUDENT_TRAINER_RATIO_NORM))

    assigned = [
        t for t in trainers
        if cid in (t.get("assigned_course_ids") or [])
        or (cname and any(cname.lower() in str(c).lower() for c in (t.get("assigned_course_ids") or [])))
    ]
    active_assigned = [t for t in assigned if t.get("status") in ("ACTIVE", "IN_TRAINING")]
    assigned_count = len(active_assigned)

    capacity_ratio_pct = min(100.0, round((assigned_count / required_trainers) * 100.0, 1))

    raw_skills = course.get("required_skills") or course.get("target_skills") or course.get("skills") or []
    if isinstance(raw_skills, list) and raw_skills and isinstance(raw_skills[0], dict):
        required_skills = [s.get("name") or s.get("skill_name") for s in raw_skills if s.get("name") or s.get("skill_name")]
    elif isinstance(raw_skills, list):
        required_skills = [str(s) for s in raw_skills if s]
    else:
        required_skills = []

    if not required_skills:
        cat = (course.get("category") or cname or "").lower()
        if "ai" in cat or "machine learning" in cat:
            required_skills = ["Python", "Machine Learning", "Deep Learning", "PyTorch", "RAG"]
        elif "ev" in cat or "electric" in cat:
            required_skills = ["EV Powertrain", "BMS Diagnostics", "High-Voltage Safety", "CAN Bus"]
        elif "robot" in cat or "automation" in cat:
            required_skills = ["PLC Programming", "SCADA", "Industrial Robotics", "Sensors & Actuators"]
        elif "cyber" in cat:
            required_skills = ["Network Security", "Ethical Hacking", "CERT-In Compliance", "Firewall Configuration"]
        else:
            required_skills = ["Technical Instruction", "Workshop Safety", "Applied Tools", "Quality Inspection"]

    certified_set = set()
    for t in active_assigned:
        for s in (t.get("certified_skills") or []):
            certified_set.add(str(s).strip().lower())

    covered_skills = [s for s in required_skills if s.strip().lower() in certified_set]
    missing_skills = [s for s in required_skills if s.strip().lower() not in certified_set]

    competency_score_pct = round((len(covered_skills) / max(1, len(required_skills))) * 100.0, 1)
    trainer_health_score = round((capacity_ratio_pct * 0.50) + (competency_score_pct * 0.50), 1)

    suggested_programs = []
    for cat_name, prog_list in TRAINER_UPGRADE_CATALOG.items():
        for p in prog_list:
            p_text = (p.get("program") or "").lower()
            if any(m.lower() in p_text for m in missing_skills):
                suggested_programs.append(p)

    return {
        "course_id": cid,
        "course_name": cname,
        "enrolment_capacity": enrolment,
        "required_trainers": required_trainers,
        "required_trainers_count": required_trainers,
        "assigned_trainers_count": assigned_count,
        "capacity_ratio_pct": capacity_ratio_pct,
        "ratio_compliant": assigned_count >= required_trainers,
        "required_skills": required_skills,
        "covered_skills": covered_skills,
        "uncovered_skills": missing_skills,
        "missing_skills": missing_skills,
        "competency_score_pct": competency_score_pct,
        "trainer_health_score": trainer_health_score,
        "assigned_trainers": [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "designation": t.get("designation"),
                "status": t.get("status"),
                "nsqf_certified_level": t.get("nsqf_certified_level"),
                "certified_skills": t.get("certified_skills", []),
            }
            for t in active_assigned
        ],
        "suggested_upskilling_programs": suggested_programs[:3],
    }


def compute_institute_faculty_scorecard(
    institute_id: str,
    institute_name: str | None = None,
    district: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if not _cache:
        init_db()
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        all_courses = _cache.get("courses", [])
    else:
        try:
            from app.repositories.supabase_repository import list_courses
            all_courses = list_courses(is_demo=is_demo) or []
        except Exception:
            all_courses = [c for c in _cache.get("courses", []) if is_demo is None or c.get("is_demo") == is_demo]

    clean_id = institute_id.strip()
    inst_courses = [
        c for c in all_courses
        if (c.get("institute_id") and c["institute_id"].lower() == clean_id.lower())
        or (institute_name and c.get("institute") and c["institute"].strip().lower() == institute_name.strip().lower())
        or (clean_id in (c.get("institute") or "").lower())
    ]
    trainers = _get_trainers(institute_id=clean_id, is_demo=is_demo)
    if not trainers and (is_demo_mode or is_demo):
        trainers = [t for t in _cache.get("institution_trainers", []) if t.get("institute_id", "").lower() == clean_id.lower()]

    resolved_name = institute_name or (inst_courses[0].get("institute") if inst_courses else (trainers[0].get("institute_name") if trainers else "State Technical Institute"))
    resolved_district = district or (inst_courses[0].get("district") if inst_courses else (trainers[0].get("district") if trainers else "Maharashtra"))

    course_capacities = [compute_course_trainer_capacity(c, trainers) for c in inst_courses]

    total_trainers = len(trainers)
    active_trainers = len([t for t in trainers if t.get("status") == "ACTIVE"])
    in_training_trainers = len([t for t in trainers if t.get("status") == "IN_TRAINING"])

    total_enrolment = sum(c.get("enrolment_capacity") or c.get("enrolment_count") or 60 for c in inst_courses)
    total_required = sum(cc["required_trainers_count"] for cc in course_capacities)
    total_assigned = sum(cc["assigned_trainers_count"] for cc in course_capacities)

    overall_ratio = round(total_enrolment / max(1, active_trainers), 1) if active_trainers > 0 else 0.0
    overall_ratio_compliant = overall_ratio > 0 and overall_ratio <= NSQF_STUDENT_TRAINER_RATIO_NORM

    avg_capacity = round(sum(cc["capacity_ratio_pct"] for cc in course_capacities) / max(1, len(course_capacities)), 1)
    avg_competency = round(sum(cc["competency_score_pct"] for cc in course_capacities) / max(1, len(course_capacities)), 1)
    faculty_readiness_index = round((avg_capacity * 0.50) + (avg_competency * 0.50), 1)

    all_missing_skills = set()
    for cc in course_capacities:
        for ms in cc["missing_skills"]:
            all_missing_skills.add(ms)

    nominations = _get_nominations(institute_id=clean_id, is_demo=is_demo)

    certified_count = len([t for t in trainers if len(t.get("certifications") or t.get("certified_skills") or []) > 0])
    ratio_str = f"1:{int(round(overall_ratio))}" if overall_ratio > 0 else "1:20"

    return {
        "institute_id": clean_id,
        "institute_name": resolved_name,
        "district": resolved_district,
        "total_faculty_count": total_trainers,
        "total_instructors": total_trainers,
        "active_faculty_count": active_trainers,
        "in_training_faculty_count": in_training_trainers,
        "certified_instructors_count": certified_count,
        "total_enrolment_capacity": total_enrolment,
        "total_enrolment": total_enrolment,
        "required_trainers_norm": total_required,
        "assigned_trainers_total": total_assigned,
        "student_to_trainer_ratio": overall_ratio,
        "overall_student_trainer_ratio": ratio_str,
        "nsqf_ratio_compliant": overall_ratio_compliant,
        "overall_compliance_status": "COMPLIANT" if overall_ratio_compliant else "UNDERSTAFFED",
        "capacity_compliance_pct": avg_capacity,
        "competency_alignment_pct": avg_competency,
        "faculty_readiness_index": faculty_readiness_index,
        "courses_audited_count": len(course_capacities),
        "priority_skill_deficits": sorted(all_missing_skills)[:8],
        "course_capacities": course_capacities,
        "course_capacity_breakdown": course_capacities,
        "active_nominations_count": len(nominations),
        "data_provenance": "INSTITUTE_AUTHORITATIVE",
    }


def compute_statewide_trainer_analytics(
    district_filter: str | None = None,
    trade_filter: str | None = None,
    is_demo: bool | None = None,
) -> dict[str, Any]:
    if not _cache:
        init_db()

    trainers = _get_trainers(district=district_filter, trade=trade_filter, is_demo=is_demo)
    nominations = _get_nominations(district=district_filter, is_demo=is_demo)

    total_faculty = len(trainers)
    active_faculty = len([t for t in trainers if t.get("status") == "ACTIVE"])
    in_training = len([t for t in trainers if t.get("status") == "IN_TRAINING"])

    emerging_trades = {"artificial intelligence", "electric vehicles", "mechatronics & robotics", "cybersecurity"}
    emerging_faculty = len([t for t in trainers if (t.get("primary_trade") or "").lower() in emerging_trades])
    emerging_faculty_pct = round((emerging_faculty / max(1, total_faculty)) * 100.0, 1)

    nomination_counts = {
        "NOMINATED": len([n for n in nominations if n.get("status") == "NOMINATED"]),
        "SANCTIONED": len([n for n in nominations if n.get("status") == "SANCTIONED"]),
        "IN_PROGRESS": len([n for n in nominations if n.get("status") == "IN_PROGRESS"]),
        "COMPLETED": len([n for n in nominations if n.get("status") == "COMPLETED"]),
        "REJECTED": len([n for n in nominations if n.get("status") == "REJECTED"]),
    }
    total_stipend_sanctioned_inr = sum(n.get("stipend_grant_inr") or n.get("sanction_amount_inr") or n.get("budget_inr") or 0 for n in nominations if n.get("status") in ("SANCTIONED", "IN_PROGRESS", "COMPLETED"))

    is_demo_mode = is_explicit_demo_mode(is_demo)
    if is_demo_mode:
        all_courses = _cache.get("courses", [])
    else:
        try:
            from app.repositories.supabase_repository import list_courses
            all_courses = list_courses(is_demo=is_demo) or []
        except Exception:
            all_courses = [c for c in _cache.get("courses", []) if is_demo is None or c.get("is_demo") == is_demo]

    district_enrolment: dict[str, int] = {}
    for c in all_courses:
        cdist = (c.get("district") or "").strip()
        if cdist:
            if district_filter and district_filter.lower() not in cdist.lower():
                continue
            enrol = c.get("enrolment_capacity") or c.get("enrolment_count") or 0
            matched_key = next((k for k in district_enrolment if k.lower() == cdist.lower()), cdist)
            district_enrolment[matched_key] = district_enrolment.get(matched_key, 0) + int(enrol)

    district_groups: dict[str, list[dict[str, Any]]] = {}
    for t in trainers:
        d = t.get("district") or "Maharashtra"
        district_groups.setdefault(d, []).append(t)

    all_districts = sorted(list(set(district_groups.keys()) | set(district_enrolment.keys())))

    district_leaderboard = []
    for d in all_districts:
        d_trainers = district_groups.get(d, [])
        d_active = len([t for t in d_trainers if t.get("status") == "ACTIVE"])
        d_emerging = len([t for t in d_trainers if (t.get("primary_trade") or "").lower() in emerging_trades])
        d_noms = [n for n in nominations if (n.get("district") or "").lower() == d.lower()]

        matched_enrol_key = next((k for k in district_enrolment if k.lower() == d.lower()), None)
        d_enrol = district_enrolment[matched_enrol_key] if matched_enrol_key else 0

        req_tr = max(1, math.ceil(d_enrol / NSQF_STUDENT_TRAINER_RATIO_NORM))
        gap = max(0, req_tr - d_active)
        comp_status = "COMPLIANT" if d_active >= req_tr else "UNDERSTAFFED"
        district_leaderboard.append({
            "district": d,
            "total_faculty": len(d_trainers),
            "trainer_count": len(d_trainers),
            "active_faculty": d_active,
            "emerging_tech_certified": d_emerging,
            "certified_count": d_emerging,
            "enrolment_capacity": d_enrol,
            "required_trainers": req_tr,
            "trainer_gap": gap,
            "faculty_readiness_index": round(min(100.0, (d_active / max(1, req_tr))) * 100.0, 1),
            "compliance_status": comp_status,
            "active_nominations": len(d_noms),
            "sanctioned_fdp_seats": len([n for n in d_noms if n.get("status") in ("SANCTIONED", "IN_PROGRESS")]),
        })

    district_leaderboard.sort(key=lambda x: x["total_faculty"], reverse=True)

    compliant_districts = len([d for d in district_leaderboard if d.get("compliance_status") == "COMPLIANT"])
    compliance_ratio_pct = round((compliant_districts / max(1, len(district_leaderboard))) * 100.0, 1)

    summary = {
        "total_trainers": total_faculty,
        "active_trainers": active_faculty,
        "certified_trainers_count": emerging_faculty,
        "statewide_compliance_ratio_pct": compliance_ratio_pct,
    }

    return {
        "district_filter": district_filter or "ALL",
        "trade_filter": trade_filter or "ALL",
        "total_faculty_tracked": total_faculty,
        "active_faculty_count": active_faculty,
        "in_training_faculty_count": in_training,
        "emerging_tech_faculty_count": emerging_faculty,
        "emerging_tech_faculty_pct": emerging_faculty_pct,
        "nomination_summary": nomination_counts,
        "total_fdp_grant_sanctioned_inr": total_stipend_sanctioned_inr,
        "district_leaderboard": district_leaderboard,
        "district_breakdown": district_leaderboard,
        "summary": summary,
        "data_provenance": "STATE_SANCTIONED_FDP",
    }
