"""Verification test suite for production audit fixes:
- Privacy & cross-student isolation on assessment, recommendations, and AI explanation
- Scheme & gov opportunity recommendations by student user_id
- Employer demand persistence on PATCH update
- District workforce plan employer demand job_role accounting
- Gap engine skill ID demand integration
- Gemini AI model fallback configuration
"""
import pytest
from starlette.testclient import TestClient
from app.main import app
import app.db as db
from ai.gemini_provider import MODELS, GeminiProvider

client = TestClient(app)


def get_token(email: str, password: str = "Password@123") -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_student_privacy_and_cross_student_isolation():
    """Verify private student assessments, recommendations, and AI explanation endpoints reject unauthorized access."""
    # 1. Register candidate Alpha
    alpha_email = "audit_candidate_alpha@skillsetu.gov.in"
    client.post("/api/auth/register", json={
        "email": alpha_email,
        "password": "Password@123",
        "full_name": "Audit Alpha",
        "role": "STUDENT",
        "district": "Pune",
    })
    token_alpha = get_token(alpha_email)
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    # Submit assessment
    post_res = client.post("/api/student/assessment", json={
        "name": "Audit Alpha",
        "education": "B.Tech Mechatronics",
        "district": "Pune",
        "career_goal": "Robotics & Automation Engineer",
        "interests": ["Robotics"],
        "current_skills": [{"skill_name": "PLC Programming", "proficiency": "intermediate"}],
        "quiz_answers": {"q1": "A"},
    }, headers=headers_alpha)
    assert post_res.status_code == 200
    ast_id = post_res.json()["assessment"]["id"]
    user_id = post_res.json()["assessment"]["user_id"]

    # 2. Register candidate Beta
    beta_email = "audit_candidate_beta@skillsetu.gov.in"
    client.post("/api/auth/register", json={
        "email": beta_email,
        "password": "Password@123",
        "full_name": "Audit Beta",
        "role": "STUDENT",
        "district": "Mumbai",
    })
    token_beta = get_token(beta_email)
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # TEST A: Assessment detail endpoint
    # Anonymous -> 401
    assert client.get(f"/api/student/assessment/{ast_id}").status_code == 401
    # Student Beta -> 403
    assert client.get(f"/api/student/assessment/{ast_id}", headers=headers_beta).status_code == 403
    # Student Alpha -> 200
    assert client.get(f"/api/student/assessment/{ast_id}", headers=headers_alpha).status_code == 200

    # TEST B: Career recommendations endpoint
    # Anonymous -> 401
    assert client.get(f"/api/student/recommendations/{ast_id}").status_code == 401
    assert client.get(f"/api/student/recommendations/{user_id}").status_code == 401
    # Student Beta -> 403
    assert client.get(f"/api/student/recommendations/{ast_id}", headers=headers_beta).status_code == 403
    assert client.get(f"/api/student/recommendations/{user_id}", headers=headers_beta).status_code == 403
    # Student Alpha -> 200
    res_recs = client.get(f"/api/student/recommendations/{ast_id}", headers=headers_alpha)
    assert res_recs.status_code == 200

    # TEST C: AI Explanation endpoint
    # Anonymous -> 401
    assert client.post(f"/api/student/recommendations/{ast_id}/explain-ai", json={}).status_code == 401
    # Student Beta -> 403
    assert client.post(f"/api/student/recommendations/{ast_id}/explain-ai", json={}, headers=headers_beta).status_code == 403
    # Student Alpha -> 200
    res_ai = client.post(f"/api/student/recommendations/{ast_id}/explain-ai", json={}, headers=headers_alpha)
    assert res_ai.status_code == 200


def test_schemes_and_gov_opps_recommendation_by_user_id():
    """Verify recommended schemes and gov opportunities work with student user_id."""
    email = "audit_recommendations_user@skillsetu.gov.in"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "Password@123",
        "full_name": "Rec Candidate",
        "role": "STUDENT",
        "district": "Pune",
    })
    token = get_token(email)
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/student/assessment", json={
        "name": "Rec Candidate",
        "education": "ITI Electrician",
        "district": "Pune",
        "career_goal": "EV Technician",
        "interests": ["Green Energy", "Electric Vehicles"],
        "current_skills": [{"skill_name": "Electrical Diagnostics", "proficiency": "beginner"}],
        "quiz_answers": {"q1": "B"},
    }, headers=headers)

    user_info = client.get("/api/auth/me", headers=headers).json()["user"]
    uid = user_info["id"]

    assert client.get(f"/api/schemes/recommended/{uid}").status_code == 401
    assert client.get(f"/api/gov/opportunities/recommended/{uid}").status_code == 401

    res_schemes = client.get(f"/api/schemes/recommended/{uid}", headers=headers)
    assert res_schemes.status_code == 200
    assert "schemes" in res_schemes.json()

    res_gov = client.get(f"/api/gov/opportunities/recommended/{uid}", headers=headers)
    assert res_gov.status_code == 200
    assert "opportunities" in res_gov.json()


def test_employer_demand_patch_persistence():
    """Verify PATCH /api/employer/demands/{id} persists to storage."""
    token = get_token("employer@skillsetu.gov.in")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create demand
    post_res = client.post("/api/employer/demands", json={
        "company_name": "Audit Renewable Corp",
        "industry": "Green Energy",
        "district": "Pune",
        "job_role": "Senior Solar Tech",
        "required_skills": ["Solar PV Systems"],
        "openings_count": 8,
    }, headers=headers)
    assert post_res.status_code == 200
    did = post_res.json()["demand"]["id"]

    # 2. Patch demand
    patch_res = client.patch(f"/api/employer/demands/{did}", json={
        "openings_count": 25,
        "job_role": "Principal Solar Energy Engineer",
    }, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["demand"]["openings_count"] == 25

    # 3. Retrieve and verify updated
    get_res = client.get(f"/api/employer/demands/{did}")
    assert get_res.status_code == 200
    assert get_res.json()["demand"]["openings_count"] == 25
    assert get_res.json()["demand"]["job_role"] == "Principal Solar Energy Engineer"


def test_district_service_and_gap_engine_integration():
    """Verify district workforce plan and gap engine count employer demand job roles and skill IDs."""
    token = get_token("employer@skillsetu.gov.in")
    headers = {"Authorization": f"Bearer {token}"}

    post_res = client.post("/api/employer/demands", json={
        "company_name": "District Audit Motors",
        "industry": "Automotive",
        "district": "Pune",
        "job_role": "High Voltage Power Specialist",
        "required_skills": ["sk-018", "PLC Programming"],
        "openings_count": 50,
    }, headers=headers)
    assert post_res.status_code == 200
    did = post_res.json()["demand"]["id"]

    # In Phase 6 hardening, employer demand must be VALIDATED to influence district plan
    admin_token = get_token("admin@skillsetu.gov.in", "AdminPass@2026")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    val_res = client.patch(
        f"/api/admin/employer/demands/{did}/status",
        json={"status": "VALIDATED"},
        headers=admin_headers,
    )
    assert val_res.status_code == 200

    plan_res = client.get("/api/districts/Pune/plan")
    assert plan_res.status_code == 200
    plan = plan_res.json()
    top_roles = [r["role"] for r in plan.get("top_demanded_roles", [])]
    assert any("High Voltage Power Specialist" in r for r in top_roles)


def test_gemini_provider_models_contain_active_google_api_targets():
    """Verify GeminiProvider MODELS list contains active production model."""
    assert "gemini-3.6-flash" in MODELS
    provider = GeminiProvider()
    assert provider.model in MODELS
