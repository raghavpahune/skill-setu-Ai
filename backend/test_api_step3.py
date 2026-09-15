"""Test suite for Task 2 Step 3: Schemes & Opportunities APIs."""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from starlette.testclient import TestClient
from app.main import app
from app.db import load_demo_data

# Ensure demo data is loaded for tests
load_demo_data()
client = TestClient(app)


def test_schemes_endpoint():
    print("Testing GET /api/schemes...")
    res = client.get("/api/schemes")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    schemes = res.json()
    assert isinstance(schemes, list) and len(schemes) >= 10, "Should return at least 10 schemes"
    first = schemes[0]
    for key in ["id", "title", "department", "scheme_type", "beneficiary_category", "application_portal_url"]:
        assert key in first, f"Missing key '{key}' in scheme"
    print(f"  OK: /api/schemes returned {len(schemes)} schemes.")

    # Test category filter
    res_sc = client.get("/api/schemes?category=SC")
    assert res_sc.status_code == 200
    for s in res_sc.json():
        cats = [c.upper() for c in s.get("beneficiary_category", [])]
        assert "SC" in cats or "OPEN" in cats or "ALL" in cats, f"Category mismatch in {s['id']}"
    print(f"  OK: category=SC filter returned {len(res_sc.json())} schemes.")

    # Test scheme_type filter
    res_hostel = client.get("/api/schemes?scheme_type=hostel_allowance")
    assert res_hostel.status_code == 200
    assert len(res_hostel.json()) >= 1
    assert res_hostel.json()[0]["scheme_type"] == "hostel_allowance"
    print(f"  OK: scheme_type=hostel_allowance returned {len(res_hostel.json())} schemes.")

    # Test course_type filter
    res_iti = client.get("/api/schemes?course_type=ITI")
    assert res_iti.status_code == 200
    assert len(res_iti.json()) >= 1
    for s in res_iti.json():
        cts = [c.lower() for c in s.get("eligible_course_types", [])]
        assert "iti" in cts, f"Course mismatch in {s['id']}"
    print(f"  OK: course_type=ITI returned {len(res_iti.json())} schemes.")

    # Test max_income filter
    res_inc = client.get("/api/schemes?max_income=500000")
    assert res_inc.status_code == 200
    for s in res_inc.json():
        ceiling = s.get("income_ceiling_annual")
        if ceiling is not None:
            assert ceiling >= 500000, f"Income ceiling {ceiling} < 500000"
    print(f"  OK: max_income=500000 returned {len(res_inc.json())} schemes.")

    # Test search query
    res_q = client.get("/api/schemes?q=Punjab")
    assert res_q.status_code == 200
    assert len(res_q.json()) >= 1
    assert "Punjabrao" in res_q.json()[0]["title"]
    print("  OK: search query ?q=Punjab returned matching scheme.")

    # Test categories summary
    res_meta = client.get("/api/schemes/categories")
    assert res_meta.status_code == 200
    meta = res_meta.json()
    assert "categories" in meta and "SC" in meta["categories"]
    assert "scheme_types" in meta and "scholarship" in meta["scheme_types"]
    print(f"  OK: /api/schemes/categories returned metadata: {meta['scheme_types']}")

    # Test single scheme lookup
    res_single = client.get("/api/schemes/sch-001?is_demo=true")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == "sch-001"

    # Test 404 on invalid scheme
    res_404 = client.get("/api/schemes/nonexistent-id-999")
    assert res_404.status_code == 404
    print("  OK: /api/schemes/{id} and 404 handling verified.")


def test_opportunities_endpoint():
    print("Testing GET /api/opportunities...")
    res = client.get("/api/opportunities")
    assert res.status_code == 200
    opps = res.json()
    assert isinstance(opps, list) and len(opps) > 0
    first = opps[0]
    for key in ["id", "title", "company", "district", "industry", "opportunity_type", "skills"]:
        assert key in first, f"Missing key '{key}' in opportunity"
    print(f"  OK: /api/opportunities returned {len(opps)} items.")

    # Test filtering by opportunity_type
    res_app = client.get("/api/opportunities?opportunity_type=apprenticeship")
    assert res_app.status_code == 200
    app_list = res_app.json()
    assert len(app_list) >= 3, f"Expected >= 3 apprenticeships, got {len(app_list)}"
    for item in app_list:
        assert item["opportunity_type"] == "apprenticeship"
        assert item.get("stipend_amount") is not None
    print(f"  OK: opportunity_type=apprenticeship returned {len(app_list)} items.")

    res_int = client.get("/api/opportunities?opportunity_type=internship")
    assert res_int.status_code == 200
    int_list = res_int.json()
    assert len(int_list) >= 2, f"Expected >= 2 internships, got {len(int_list)}"
    for item in int_list:
        assert item["opportunity_type"] == "internship"
    print(f"  OK: opportunity_type=internship returned {len(int_list)} items.")

    # Test filtering by district
    res_pune = client.get("/api/opportunities?district=Pune")
    assert res_pune.status_code == 200
    for item in res_pune.json():
        assert item["district"].lower() == "pune"
    print(f"  OK: district=Pune returned {len(res_pune.json())} items.")

    # Test filtering by skill
    res_skill = client.get("/api/opportunities?skill=Python")
    assert res_skill.status_code == 200
    for item in res_skill.json():
        skill_names = [s["skill_name"].lower() for s in item.get("skills", [])]
        assert any("python" in sn for sn in skill_names), f"Skill mismatch in {item['id']}"
    print(f"  OK: skill=Python returned {len(res_skill.json())} items.")

    # Test filtering by min_stipend
    res_stipend = client.get("/api/opportunities?min_stipend=12000")
    assert res_stipend.status_code == 200
    for item in res_stipend.json():
        assert item["stipend_amount"] >= 12000
    print(f"  OK: min_stipend=12000 returned {len(res_stipend.json())} items.")

    # Test summary endpoint
    res_summary = client.get("/api/opportunities/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert "total_opportunities" in summary
    assert "by_type" in summary
    assert "job" in summary["by_type"]
    assert "apprenticeship" in summary["by_type"]
    print(f"  OK: /api/opportunities/summary returned breakdown: {summary['by_type']}")

    # Test single opportunity lookup
    res_single = client.get("/api/opportunities/opp-001")
    assert res_single.status_code == 200
    single = res_single.json()
    assert single["id"] == "opp-001"
    assert len(single["skills"]) >= 1
    print(f"  OK: /api/opportunities/opp-001 returned with {len(single['skills'])} skills.")

    # Test 404
    res_404 = client.get("/api/opportunities/nonexistent-opp-999")
    assert res_404.status_code == 404
    print("  OK: /api/opportunities/{id} 404 verified.")


def test_backward_compatibility():
    print("Testing backward compatibility of existing endpoints...")
    # GET /api/jobs
    res_jobs = client.get("/api/jobs")
    assert res_jobs.status_code == 200
    assert len(res_jobs.json()) == 50  # default limit 50
    print("  OK: /api/jobs works as before.")

    # GET /api/jobs?district=Pune
    res_pune = client.get("/api/jobs?district=Pune&limit=10")
    assert res_pune.status_code == 200
    assert len(res_pune.json()) <= 10
    print("  OK: /api/jobs with filters works.")

    # GET /api/skills
    res_skills = client.get("/api/skills")
    assert res_skills.status_code == 200
    assert len(res_skills.json()) >= 50
    print("  OK: /api/skills works.")

    # GET /api/gaps
    res_gaps = client.get("/api/gaps")
    assert res_gaps.status_code == 200
    print(f"  OK: /api/gaps returned {len(res_gaps.json())} gaps.")

    # GET /api/health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    print("  OK: /api/health returned ok.")


if __name__ == "__main__":
    test_schemes_endpoint()
    test_opportunities_endpoint()
    test_backward_compatibility()
    print("\nALL BACKEND API TESTS PASSED SUCCESSFULLY!")
