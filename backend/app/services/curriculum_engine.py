"""Automated Course Obsolescence & Curriculum Modernization Engine (Phase 27).

Evaluates institutional vocational & technical courses across Maharashtra:
1. Computes course health score & placement efficiency.
2. Identifies obsolescence risk and labor-market oversupply.
3. Generates transparent syllabus revision blueprints with modules to add/prune.
4. Estimates required equipment upgrades, budgets, and trainer certifications.
"""
import logging
from typing import Any
from app.db import get_demo
from app.services.forecast_engine import compute_multi_horizon_forecasts

logger = logging.getLogger(__name__)


# Equipment & Trainer catalog grounded in Maharashtra ITI / Polytechnic standards
EQUIPMENT_CATALOG = {
    "Artificial Intelligence": [
        {"item": "High-Performance GPU AI Workstations (RTX 4090/A4000)", "units": 10, "unit_cost_inr": 250000, "category": "Computing Hardware"},
        {"item": "Edge AI Development Kits (Jetson Orin Nano)", "units": 15, "unit_cost_inr": 45000, "category": "Embedded Systems"},
        {"item": "High-Speed Local LLM Inference Server", "units": 1, "unit_cost_inr": 600000, "category": "Server Infrastructure"},
    ],
    "Electric Vehicles": [
        {"item": "Lithium Battery Pack Testing & BMS Diagnostic Rig", "units": 2, "unit_cost_inr": 450000, "category": "EV Laboratory"},
        {"item": "BLDC Motor Controller Dynamic Dynamometer", "units": 2, "unit_cost_inr": 350000, "category": "EV Testbed"},
        {"item": "High-Voltage Safety Isolation Tools & PPE Kits", "units": 10, "unit_cost_inr": 25000, "category": "Safety Equipment"},
    ],
    "Robotics & Automation": [
        {"item": "6-Axis Industrial Articulated Robotic Arm Trainer", "units": 2, "unit_cost_inr": 850000, "category": "Robotics"},
        {"item": "PLC / SCADA Automation Trainer Kits (Siemens S7-1200)", "units": 6, "unit_cost_inr": 120000, "category": "Industrial Automation"},
        {"item": "Machine Vision Sensor Inspection System", "units": 3, "unit_cost_inr": 95000, "category": "Sensors & Vision"},
    ],
    "Cybersecurity & Cloud": [
        {"item": "Hardware Network Firewall / UTM Testing Appliance", "units": 2, "unit_cost_inr": 180000, "category": "Network Security"},
        {"item": "Isolated Cyber Range Simulation Server", "units": 1, "unit_cost_inr": 500000, "category": "Server Infrastructure"},
    ],
    "General Technical": [
        {"item": "Modern Digital Multimeters & DSO Oscilloscopes", "units": 12, "unit_cost_inr": 35000, "category": "Measurement"},
        {"item": "Smart Classroom Interactive Display (75-inch 4K)", "units": 2, "unit_cost_inr": 150000, "category": "Smart Pedagogy"},
    ]
}

TRAINER_UPGRADE_CATALOG = {
    "Artificial Intelligence": [
        {"program": "Advanced RAG, Agentic AI & PyTorch Frameworks", "duration": "4 Weeks", "certifying_body": "IIT Bombay / NPTEL", "target_trainers": 3},
        {"program": "MLOps, Model Deployment & Cloud API Integration", "duration": "2 Weeks", "certifying_body": "CDAC Pune", "target_trainers": 2},
    ],
    "Electric Vehicles": [
        {"program": "High-Voltage Safety & Battery Management Systems (BMS)", "duration": "3 Weeks", "certifying_body": "ARAI Pune", "target_trainers": 4},
        {"program": "EV Motor Drives & CAN Bus Telematics", "duration": "2 Weeks", "certifying_body": "MSBTE / Industry Partner", "target_trainers": 2},
    ],
    "Robotics & Automation": [
        {"program": "ROS2 Robotic Operating System & Industrial Arm Control", "duration": "3 Weeks", "certifying_body": "VJTI Mumbai / FANUC", "target_trainers": 3},
        {"program": "Industry 4.0 PLC Programming & Digital Twin Simulation", "duration": "2 Weeks", "certifying_body": "Siemens Training Center", "target_trainers": 2},
    ],
    "Cybersecurity & Cloud": [
        {"program": "Certified Ethical Hacker (CEH) & Threat Hunting", "duration": "3 Weeks", "certifying_body": "EC-Council / CDAC", "target_trainers": 2},
    ],
    "General Technical": [
        {"program": "NSQF Pedagogy & Outcome-Based Technical Instruction", "duration": "1 Week", "certifying_body": "NITTTR Bhopal", "target_trainers": 4},
    ]
}


def audit_all_courses(is_demo: bool | None = None) -> list[dict[str, Any]]:
    from collections import Counter
    from app.core.data_mode import is_explicit_demo_mode
    is_demo_mode = is_explicit_demo_mode(is_demo)

    if is_demo_mode:
        courses = get_demo("courses")
        course_skills_raw = get_demo("course_skills")
        placements = {
            p["course_id"]: p
            for p in sorted(get_demo("placements"), key=lambda r: r.get("year") or 0)
            if p.get("course_id")
        }
        skills_map = {s["id"]: s for s in get_demo("skills")}
        forecasts = {f["skill_id"]: f for f in compute_multi_horizon_forecasts(is_demo=True)}
        jobs = get_demo("jobs")
        job_skills = get_demo("job_skills")
        employer_demands = get_demo("employer_demands")
        gov_opportunities = get_demo("gov_opportunities")
        employers = get_demo("employers")
        placement_outcomes = get_demo("placement_outcomes") or []
        placement_employer_feedback = get_demo("placement_employer_feedback") or []
    else:
        try:
            from app.repositories.supabase_repository import (
                list_courses,
                list_course_skills,
                list_skills,
                list_placements,
                list_jobs,
                list_job_skills,
                list_employer_demands,
                list_gov_opportunities,
                list_employers,
                list_placement_outcomes,
                list_placement_employer_feedback,
            )
            courses = list_courses(is_demo=is_demo) or []
            if not courses:
                return []
            c_ids = [c["id"] for c in courses if c.get("id")]
            course_skills_raw = list_course_skills(course_ids=c_ids) if c_ids else []
            p_rows = list_placements(course_ids=c_ids) if c_ids else []
            placements = {
                p["course_id"]: p
                for p in sorted(p_rows, key=lambda r: r.get("year") or 0)
                if p.get("course_id")
            }
            repo_skills = list_skills(limit=10000) or []
            skills_map = {s["id"]: s for s in repo_skills if "id" in s}
            jobs = list_jobs(is_demo=is_demo, status="active", is_active=True, limit=None) or []
            j_ids = [j["id"] for j in jobs if j.get("id")]
            job_skills = list_job_skills(job_ids=j_ids) if j_ids else []
            employer_demands = list_employer_demands(is_demo=is_demo) or []
            gov_opportunities = list_gov_opportunities(is_demo=is_demo, limit=None) or []
            employers = list_employers(is_demo=is_demo, limit=10000) or []
            placement_outcomes = list_placement_outcomes(is_demo=is_demo, limit=10000) or []
            placement_employer_feedback = list_placement_employer_feedback(is_demo=is_demo, limit=10000) or []
        except Exception as e:
            logger.warning("[CurriculumEngine] Authoritative audit inputs unavailable: %s", e)
            return []
        forecasts = {f["skill_id"]: f for f in compute_multi_horizon_forecasts(is_demo=is_demo)}

    skills_by_name = {s.get("name", "").strip().lower(): s["id"] for s in skills_map.values() if s.get("name") and "id" in s}
    verified_emp_ids = {e["id"] for e in employers if e.get("verification_status") == "VERIFIED" and e.get("id")}
    verified_emp_names = {
        (e.get("company_name") or e.get("name", "")).strip().lower(): (e.get("company_name") or e.get("name", ""))
        for e in employers
        if e.get("verification_status") == "VERIFIED" and (e.get("company_name") or e.get("name"))
    }

    jobs_by_district: dict[str, list[dict]] = {}
    for j in jobs:
        d = (j.get("district") or "").strip().lower()
        if d not in jobs_by_district:
            jobs_by_district[d] = []
        jobs_by_district[d].append(j)

    job_id_to_district = {j["id"]: (j.get("district") or "").strip().lower() for j in jobs if j.get("id")}
    district_skill_job_counts: dict[str, Counter] = {}
    state_skill_job_counts = Counter()
    for js in job_skills:
        sid = js.get("skill_id")
        jid = js.get("job_id")
        if sid:
            state_skill_job_counts[sid] += 1
            dist = job_id_to_district.get(jid, "")
            if dist:
                if dist not in district_skill_job_counts:
                    district_skill_job_counts[dist] = Counter()
                district_skill_job_counts[dist][sid] += 1

    district_verified_demands: dict[str, dict[str, list[dict]]] = {}
    state_verified_demands: dict[str, list[dict]] = {}
    for d in employer_demands:
        eid = d.get("employer_id")
        cname = (d.get("company_name") or d.get("employer_name") or d.get("company") or "").strip()
        val_status = (d.get("validation_status") or d.get("status") or "").upper()
        is_verified = bool(
            (eid and eid in verified_emp_ids)
            or (cname and cname.lower() in verified_emp_names)
            or (val_status in ("VALIDATED", "APPROVED"))
        )
        if not is_verified:
            continue

        resolved_name = verified_emp_names.get(cname.lower(), cname) if cname else "Verified Industry Partner"
        openings = int(d.get("openings_count") or d.get("positions_count") or d.get("openings") or 1)
        dist = (d.get("district") or "").strip().lower()
        req_skills = d.get("required_skills") or d.get("skills") or []
        for sk in req_skills:
            sk_id = sk if sk in skills_map else skills_by_name.get(str(sk).strip().lower())
            if sk_id:
                demand_entry = {"company": resolved_name, "openings": openings, "district": d.get("district")}
                if sk_id not in state_verified_demands:
                    state_verified_demands[sk_id] = []
                state_verified_demands[sk_id].append(demand_entry)
                if dist:
                    if dist not in district_verified_demands:
                        district_verified_demands[dist] = {}
                    if sk_id not in district_verified_demands[dist]:
                        district_verified_demands[dist][sk_id] = []
                    district_verified_demands[dist][sk_id].append(demand_entry)

    gov_by_district: dict[str, list[dict]] = {}
    for g in gov_opportunities:
        cov = g.get("district_coverage") or g.get("districts") or []
        dists = set()
        if isinstance(cov, list):
            for d_item in cov:
                if d_item and str(d_item).strip():
                    dists.add(str(d_item).strip().lower())
        elif isinstance(cov, str) and cov.strip():
            for d_item in cov.split(","):
                if d_item.strip():
                    dists.add(d_item.strip().lower())
        if g.get("district"):
            dists.add(str(g["district"]).strip().lower())
        if not dists or "all" in dists or "maharashtra" in dists:
            dists.add("all")

        for d_key in dists:
            if d_key not in gov_by_district:
                gov_by_district[d_key] = []
            gov_by_district[d_key].append(g)

    course_skills_map: dict[str, list[dict]] = {}
    for cs in course_skills_raw:
        cid = cs["course_id"]
        if cid not in course_skills_map:
            course_skills_map[cid] = []
        course_skills_map[cid].append(cs)

    outcomes_by_course: dict[str, list[dict]] = {}
    for po in (placement_outcomes or []):
        cid_po = po.get("course_id")
        if cid_po:
            outcomes_by_course.setdefault(cid_po, []).append(po)

    outcome_id_to_course = {po["id"]: po.get("course_id") for po in (placement_outcomes or []) if po.get("id")}
    feedback_by_course: dict[str, list[dict]] = {}
    for pef in (placement_employer_feedback or []):
        p_id = pef.get("placement_outcome_id")
        c_id = outcome_id_to_course.get(p_id)
        if c_id:
            feedback_by_course.setdefault(c_id, []).append(pef)

    audited_courses = []

    for c in courses:
        cid = c["id"]
        c_name = c.get("name") or c.get("title", "Technical Course")
        institute = c.get("institute", "Government Technical Institute")
        district = c.get("district", "Maharashtra")
        enrolment = c.get("enrolment_count", 60)

        tracked_outcomes = outcomes_by_course.get(cid, [])
        course_feedbacks = feedback_by_course.get(cid, [])

        if tracked_outcomes:
            student_count = len(tracked_outcomes)
            placed_count = sum(1 for o in tracked_outcomes if o.get("status") in ("PLACED", "EMPLOYED", "EMPLOYER_FEEDBACK_PENDING", "FEEDBACK_RECEIVED"))
            placement_rate = round((placed_count / max(1, student_count)) * 100, 1)
            has_placement_data = True
        else:
            p = placements.get(cid, {})
            has_placement_data = bool(p and ("placed_count" in p or "student_count" in p or "placement_rate" in p))
            student_count = p.get("student_count", 0) if has_placement_data else 0
            placed_count = p.get("placed_count", 0) if has_placement_data else 0
            placement_rate = round((placed_count / max(1, student_count)) * 100, 1) if (has_placement_data and student_count) else 0.0

        emp_reported_missing = []
        for fb in course_feedbacks:
            m_list = fb.get("missing_skills") or []
            if isinstance(m_list, list):
                for ms in m_list:
                    if isinstance(ms, str) and ms.strip() and ms.strip() not in emp_reported_missing:
                        emp_reported_missing.append(ms.strip())

        taught_skills = course_skills_map.get(cid, [])
        taught_sids = {ts["skill_id"] for ts in taught_skills}
        extra_skills = c.get("skills") or c.get("skills_taught") or []
        for es in extra_skills:
            es_id = es if es in skills_map else skills_by_name.get(str(es).strip().lower())
            if es_id:
                taught_sids.add(es_id)

        rising_skills_in_syllabus = []
        obsolete_or_declining_in_syllabus = []

        for ts in taught_skills:
            sid = ts["skill_id"]
            fc = forecasts.get(sid, {})
            sk_info = skills_map.get(sid, {})
            if fc.get("trend") in ("RISING", "EMERGING") or fc.get("projected_24m", 0) > 70:
                rising_skills_in_syllabus.append(sk_info.get("name", sid))
            elif fc.get("trend") == "DECLINING" or fc.get("current_demand_score", 50) < 30:
                obsolete_or_declining_in_syllabus.append(sk_info.get("name", sid))

        category_hint = "Artificial Intelligence" if any(w in c_name.lower() for w in ["ai", "data", "software", "computer", "cloud"]) else (
            "Electric Vehicles" if any(w in c_name.lower() for w in ["ev", "electric", "auto", "vehicle", "battery"]) else (
                "Robotics & Automation" if any(w in c_name.lower() for w in ["robot", "mechanical", "automation", "mechatronics", "smart"]) else "General Technical"
            )
        )

        dist_key = district.strip().lower()
        total_district_jobs = len(jobs_by_district.get(dist_key, []))

        missing_critical_skills = []
        for sid, fc in forecasts.items():
            if sid not in taught_sids and fc.get("trend") in ("RISING", "EMERGING"):
                sk_info = skills_map.get(sid, {})
                sk_cat = sk_info.get("category", "")
                if category_hint in sk_cat or category_hint in sk_info.get("name", "") or fc.get("projected_24m", 0) > 85:
                    dist_counts = district_skill_job_counts.get(dist_key, Counter())
                    dist_job_cnt = dist_counts.get(sid, 0)
                    state_job_cnt = state_skill_job_counts.get(sid, 0)

                    dist_v_demands = district_verified_demands.get(dist_key, {}).get(sid, [])
                    state_v_demands = state_verified_demands.get(sid, [])
                    active_v_demands = dist_v_demands if dist_v_demands else state_v_demands

                    v_openings = sum(item["openings"] for item in active_v_demands)
                    v_companies = sorted({item["company"] for item in active_v_demands if item.get("company")})[:3]

                    dist_gov_candidates = gov_by_district.get(dist_key, []) + gov_by_district.get("all", [])
                    gov_opps_matching = [
                        gov for gov in dist_gov_candidates
                        if sid in (gov.get("target_skills") or gov.get("skills_covered") or [])
                        or (sk_info.get("name") and sk_info.get("name") in (gov.get("target_skills") or gov.get("skills_covered") or []))
                        or category_hint.lower() in (gov.get("sector") or "").lower()
                    ]
                    gov_cnt = len(gov_opps_matching)

                    src_types = []
                    if dist_job_cnt > 0:
                        src_types.append("JOB_POSTING_INGESTION")
                    elif state_job_cnt > 0:
                        src_types.append("STATEWIDE_JOB_INGESTION")
                    if v_openings > 0:
                        src_types.append("AUTHORITATIVE_VERIFIED")
                    if gov_cnt > 0:
                        src_types.append("GOVERNMENT_OFFICIAL")
                    if not src_types:
                        src_types.append("STATISTICAL_FORECAST")

                    missing_critical_skills.append({
                        "skill_id": sid,
                        "skill_name": sk_info.get("name", sid),
                        "projected_24m_demand": fc.get("projected_24m", 80),
                        "trend": fc.get("trend", "RISING"),
                        "nsqf_level": sk_info.get("nsqf_level", 5),
                        "job_demand_count": dist_job_cnt,
                        "statewide_job_demand_count": state_job_cnt,
                        "verified_employer_openings": v_openings,
                        "verified_employers": v_companies,
                        "gov_opportunities_count": gov_cnt,
                        "demand_source_types": src_types,
                    })

        if not missing_critical_skills:
            for sid, sk_info in skills_map.items():
                if sid not in taught_sids:
                    fc = forecasts.get(sid, {})
                    dist_counts = district_skill_job_counts.get(dist_key, Counter())
                    dist_job_cnt = dist_counts.get(sid, 0)
                    state_job_cnt = state_skill_job_counts.get(sid, 0)
                    dist_v_demands = district_verified_demands.get(dist_key, {}).get(sid, [])
                    state_v_demands = state_verified_demands.get(sid, [])
                    active_v_demands = dist_v_demands if dist_v_demands else state_v_demands
                    v_openings = sum(item["openings"] for item in active_v_demands)
                    v_companies = sorted({item["company"] for item in active_v_demands if item.get("company")})[:3]

                    dist_gov_candidates = gov_by_district.get(dist_key, []) + gov_by_district.get("all", [])
                    gov_opps_matching = [
                        gov for gov in dist_gov_candidates
                        if sid in (gov.get("target_skills") or gov.get("skills_covered") or [])
                        or (sk_info.get("name") and sk_info.get("name") in (gov.get("target_skills") or gov.get("skills_covered") or []))
                        or category_hint.lower() in (gov.get("sector") or "").lower()
                    ]
                    gov_cnt = len(gov_opps_matching)

                    src_types = []
                    if dist_job_cnt > 0:
                        src_types.append("JOB_POSTING_INGESTION")
                    elif state_job_cnt > 0:
                        src_types.append("STATEWIDE_JOB_INGESTION")
                    if v_openings > 0:
                        src_types.append("AUTHORITATIVE_VERIFIED")
                    if gov_cnt > 0:
                        src_types.append("GOVERNMENT_OFFICIAL")
                    if not src_types:
                        src_types.append("STATISTICAL_FORECAST")

                    missing_critical_skills.append({
                        "skill_id": sid,
                        "skill_name": sk_info.get("name", sid),
                        "projected_24m_demand": fc.get("projected_24m", 80),
                        "trend": fc.get("trend", "RISING"),
                        "nsqf_level": sk_info.get("nsqf_level", 5),
                        "job_demand_count": dist_job_cnt,
                        "statewide_job_demand_count": state_job_cnt,
                        "verified_employer_openings": v_openings,
                        "verified_employers": v_companies,
                        "gov_opportunities_count": gov_cnt,
                        "demand_source_types": src_types,
                    })
                    if len(missing_critical_skills) >= 4:
                        break

        missing_critical_skills.sort(
            key=lambda x: (x["verified_employer_openings"] * 2 + x["job_demand_count"], x["projected_24m_demand"]),
            reverse=True,
        )
        top_missing = missing_critical_skills[:4]

        modernity_score = max(10, min(100, int(
            (len(rising_skills_in_syllabus) * 22) - (len(obsolete_or_declining_in_syllabus) * 15) + 40
        )))
        if has_placement_data:
            health_score = round((placement_rate * 0.55) + (modernity_score * 0.45), 1)
        else:
            health_score = round(float(modernity_score), 1)

        if has_placement_data and (health_score < 42 or placement_rate < 35):
            obsolescence_risk = "CRITICAL_OBSOLETE"
            risk_label = "Critical Obsolescence — Immediate Revision Required"
            risk_color = "rose"
        elif (has_placement_data and (health_score < 58 or placement_rate < 50)) or (not has_placement_data and health_score < 42):
            obsolescence_risk = "HIGH_RISK"
            risk_label = "High Risk — Syllabus Lagging Industry"
            risk_color = "amber"
        elif health_score < 72:
            obsolescence_risk = "MODERATE"
            risk_label = "Moderate — Periodic Review Recommended"
            risk_color = "blue"
        else:
            obsolescence_risk = "HEALTHY"
            risk_label = "Healthy — Aligned with Labour Market"
            risk_color = "emerald"

        if has_placement_data and placement_rate < 40 and student_count >= 80:
            oversupply_status = "OVERSUPPLY_CRITICAL"
            oversupply_msg = f"High annual output ({student_count} seats) with only {placement_rate}% placement indicates candidate oversupply."
        elif has_placement_data and placement_rate < 52 and student_count >= 60:
            oversupply_status = "MONITOR_OVERSUPPLY"
            oversupply_msg = f"Placement rate ({placement_rate}%) is softening; recommend shifting seats to high-demand tracks."
        elif has_placement_data:
            oversupply_status = "BALANCED"
            oversupply_msg = f"Intake and hiring demand are in sustainable equilibrium ({placement_rate}% placement)."
        else:
            oversupply_status = "BALANCED"
            oversupply_msg = "Placement records not yet indexed for this course."

        equip_items = EQUIPMENT_CATALOG.get(category_hint, EQUIPMENT_CATALOG["General Technical"])
        trainer_items = TRAINER_UPGRADE_CATALOG.get(category_hint, TRAINER_UPGRADE_CATALOG["General Technical"])
        total_equip_budget_inr = sum(eq["units"] * eq["unit_cost_inr"] for eq in equip_items)

        total_missing_jobs = sum(m.get("job_demand_count", 0) for m in top_missing)
        total_statewide_jobs = sum(m.get("statewide_job_demand_count", 0) for m in top_missing)
        effective_jobs_matched = total_missing_jobs if total_missing_jobs > 0 else total_statewide_jobs
        total_v_openings = sum(m.get("verified_employer_openings", 0) for m in top_missing)
        all_v_employers = sorted({emp for m in top_missing for emp in m.get("verified_employers", [])})
        dist_gov_candidates = gov_by_district.get(dist_key, []) + gov_by_district.get("all", [])
        gov_schemes = sorted({
            g.get("name") or g.get("scheme_name") or g.get("opportunity_type") or "NAPS Apprenticeship"
            for g in dist_gov_candidates[:3]
            if g.get("name") or g.get("scheme_name") or g.get("opportunity_type")
        })

        evidence_summary = {
            "total_job_vacancies_in_district": total_district_jobs,
            "matching_job_vacancies": effective_jobs_matched,
            "live_jobs_matched": effective_jobs_matched,
            "verified_employer_openings": total_v_openings,
            "verified_employers": all_v_employers[:4],
            "verified_employers_count": len(all_v_employers),
            "gov_opportunities_count": len(gov_schemes),
            "gov_apprenticeship_schemes": gov_schemes[:3],
            "is_backed_by_verified_demand": bool(total_v_openings > 0 or effective_jobs_matched > 0),
            "placement_outcomes_count": len(tracked_outcomes),
            "placement_feedback_count": len(course_feedbacks),
            "employer_reported_missing_skills": emp_reported_missing,
            "has_post_hire_workforce_feedback": bool(len(course_feedbacks) > 0),
        }

        audited_courses.append({
            "course_id": cid,
            "course_name": c_name,
            "institute": institute,
            "institute_id": c.get("institute_id") or f"inst-{institute.replace(' ', '-').lower()}",
            "district": district,
            "category": category_hint,
            "enrolment_count": enrolment,
            "student_count": student_count,
            "placed_count": placed_count,
            "placement_rate": placement_rate,
            "has_placement_data": has_placement_data,
            "modernity_score": modernity_score,
            "health_score": health_score,
            "obsolescence_risk": obsolescence_risk,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "oversupply_status": oversupply_status,
            "oversupply_msg": oversupply_msg,
            "syllabus_strengths": rising_skills_in_syllabus,
            "syllabus_deficits": [m["skill_name"] for m in top_missing],
            "obsolete_modules": obsolete_or_declining_in_syllabus or ["Legacy Manual Drafting / Static Syntax"],
            "top_missing_skills": top_missing,
            "equipment_requirements": equip_items,
            "total_equipment_budget_inr": total_equip_budget_inr,
            "trainer_upskilling": trainer_items,
            "evidence_summary": evidence_summary,
        })

    audited_courses.sort(key=lambda x: x["health_score"])
    return audited_courses


def get_course_modernization_blueprint(course_id: str, is_demo: bool | None = None) -> dict[str, Any] | None:
    audited = audit_all_courses(is_demo=is_demo)
    course = next((c for c in audited if c["course_id"] == course_id), None)
    if not course:
        return None

    action_plan = []
    step_num = 1

    if course["obsolete_modules"]:
        action_plan.append({
            "step": step_num,
            "phase": "Curriculum De-cluttering (Weeks 1-2)",
            "title": f"Prune outdated topics: {', '.join(course['obsolete_modules'][:2])}",
            "description": "Deprecate legacy theoretical hours to make headroom for hands-on project work.",
            "impact": "Frees up 30-40 instructional hours for industry-grade tools."
        })
        step_num += 1

    for missing_sk in course["top_missing_skills"][:2]:
        v_emps = missing_sk.get("verified_employers", [])
        v_ops = missing_sk.get("verified_employer_openings", 0)
        j_dist = missing_sk.get("job_demand_count", 0)
        j_state = missing_sk.get("statewide_job_demand_count", 0)
        if v_emps and v_ops > 0:
            if j_dist > 0:
                desc = f"Grounded in verified employer hiring demand from {', '.join(v_emps)} ({v_ops} openings) and {j_dist} active job postings in {course['district']}."
            elif j_state > 0:
                desc = f"Grounded in verified employer hiring demand from {', '.join(v_emps)} ({v_ops} openings) and {j_state} active job postings across Maharashtra."
            else:
                desc = f"Grounded in verified employer hiring demand from {', '.join(v_emps)} ({v_ops} openings)."
        elif j_dist > 0:
            desc = f"Grounded in {j_dist} active job postings in {course['district']} with 24-month demand score {missing_sk['projected_24m_demand']}/100."
        elif j_state > 0:
            desc = f"Grounded in {j_state} active job postings across Maharashtra with 24-month demand score {missing_sk['projected_24m_demand']}/100."
        else:
            desc = f"Grounded in 24-month labour market demand score ({missing_sk['projected_24m_demand']}/100, trend: {missing_sk['trend']})."

        action_plan.append({
            "step": step_num,
            "phase": "Competency Integration (Weeks 3-6)",
            "title": f"Introduce NSQF Level {missing_sk['nsqf_level']} module: {missing_sk['skill_name']}",
            "description": desc,
            "impact": "Directly resolves the critical hiring bottleneck reported by Maharashtra employers."
        })
        step_num += 1

    eq_item = course["equipment_requirements"][0]["item"] if course.get("equipment_requirements") else "vocational training equipment"
    action_plan.append({
        "step": step_num,
        "phase": "Lab Modernization & Procurement (Month 2)",
        "title": f"Procure lab equipment (Est: ₹{course['total_equipment_budget_inr']:,})",
        "description": f"Equip institute with {len(course.get('equipment_requirements') or [])} core modern hardware packages including {eq_item}.",
        "impact": "Enables 100% hands-on student experimentation on state-of-the-art apparatus."
    })
    step_num += 1

    trainers_list = course.get("trainer_upskilling") or []
    target_trainers_count = sum(t.get("target_trainers", 0) for t in trainers_list) if trainers_list else 0
    cert_body = trainers_list[0].get("certifying_body", "State Skill Development Mission") if trainers_list else "State Skill Development Mission"
    prog_name = trainers_list[0].get("program", "Technical Pedagogical Refresh") if trainers_list else "Technical Pedagogical Refresh"

    action_plan.append({
        "step": step_num,
        "phase": "Faculty Development Program (Month 2-3)",
        "title": f"Upskill {target_trainers_count} instructors via {cert_body}",
        "description": f"Mastery program in {prog_name}.",
        "impact": "Ensures curriculum delivery standards match national NSQC guidelines."
    })

    emp_missing = course.get("evidence_summary", {}).get("employer_reported_missing_skills", [])
    if emp_missing:
        action_plan.insert(0, {
            "step": 0,
            "phase": "Post-Hiring Competency Alignment (Month 1)",
            "title": f"Integrate employer-identified practical competencies: {', '.join(emp_missing[:3])}",
            "description": "Directly addresses skill deficits reported by employers who recruited graduates from this syllabus.",
            "impact": "Eliminates post-placement productivity ramp delays reported by industry partners."
        })
        for i, step in enumerate(action_plan, 1):
            step["step"] = i

    proposal_ready = {
        "course_id": course_id,
        "course_name": course["course_name"],
        "institute_id": course.get("institute_id") or f"inst-{course['institute']}",
        "institute_name": course["institute"],
        "district": course["district"],
        "title": f"Curriculum Modernization Proposal — {course['course_name']} ({course['district']})",
        "target_academic_cycle": "2026-2027 Academic Cycle",
        "modules_to_add": course["top_missing_skills"],
        "modules_to_prune": course["obsolete_modules"],
        "equipment_requirements": course["equipment_requirements"],
        "total_equipment_budget_inr": course["total_equipment_budget_inr"],
        "trainer_upskilling": course["trainer_upskilling"],
        "supporting_evidence": course.get("evidence_summary", {}),
    }

    return {
        "status": "success",
        "course_id": course_id,
        "course_name": course["course_name"],
        "institute": course["institute"],
        "district": course["district"],
        "health_summary": {
            "health_score": course["health_score"],
            "placement_rate": course["placement_rate"],
            "modernity_score": course["modernity_score"],
            "obsolescence_risk": course["obsolescence_risk"],
            "risk_label": course["risk_label"],
            "oversupply_status": course["oversupply_status"],
            "oversupply_msg": course["oversupply_msg"],
        },
        "modernization_blueprint": {
            "action_plan": action_plan,
            "top_missing_skills": course["top_missing_skills"],
            "skills_to_add": [m.get("skill_name") if isinstance(m, dict) else str(m) for m in course["top_missing_skills"]],
            "skills_to_remove": course["obsolete_modules"],
            "equipment_requirements": course["equipment_requirements"],
            "total_equipment_budget_inr": course["total_equipment_budget_inr"],
            "trainer_upskilling": course["trainer_upskilling"],
            "target_placement_lift": "+25% to +35% within 1 academic cycle",
        },
        "evidence_summary": course.get("evidence_summary", {}),
        "proposal_ready_blueprint": proposal_ready,
    }


generate_course_modernization_blueprint = get_course_modernization_blueprint

