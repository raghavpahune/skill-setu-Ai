import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.repositories.supabase_repository import (
    create_gov_opportunity,
    get_gov_opportunity,
    list_gov_opportunities,
    update_gov_opportunity_repo,
    delete_gov_opportunity_repo,
    upsert_gov_opportunities,
    create_scheme,
    get_scheme,
    list_schemes,
    update_scheme_repo,
    delete_scheme_repo,
    upsert_schemes,
    GovOpportunityNotFoundError,
    SchemeNotFoundError,
    SupabaseRepositoryError,
)

client = TestClient(app)
ADMIN_KEY = "demo-admin-key-2026"


def test_gov_opportunity_repository_crud():
    opp_data = {
        "id": "gov-test-crud-1",
        "name": "State Solar Installation Apprenticeship",
        "department": "Energy Department",
        "description": "Solar PV technician certification course",
        "eligibility_criteria": "10th pass",
        "target_skills": ["Solar", "Electrical"],
        "district_coverage": ["Pune", "Nagpur"],
        "opportunity_type": "APPRENTICESHIP",
        "application_url": "https://energy.maharashtra.gov.in",
        "deadline": "2028-12-31",
        "status": "active",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }

    created = create_gov_opportunity(opp_data)
    assert created["id"] == "gov-test-crud-1"
    assert created["name"] == opp_data["name"]

    fetched = get_gov_opportunity("gov-test-crud-1")
    assert fetched is not None
    assert fetched["id"] == "gov-test-crud-1"
    assert fetched["status"] == "active"

    updated = update_gov_opportunity_repo("gov-test-crud-1", {"status": "inactive"})
    assert updated["status"] == "inactive"

    deleted = delete_gov_opportunity_repo("gov-test-crud-1")
    assert deleted is True

    fetched_after_delete = get_gov_opportunity("gov-test-crud-1")
    assert fetched_after_delete is None

    with pytest.raises(GovOpportunityNotFoundError):
        update_gov_opportunity_repo("gov-nonexistent-id", {"status": "active"})


def test_scheme_repository_crud():
    scheme_data = {
        "id": "77777777-7777-7777-7777-777777777777",
        "scheme_code": "SCH-TEST-PH12",
        "title": "Vocational Excellence Stipend Scheme",
        "department": "Higher & Technical Education",
        "scheme_type": "stipend",
        "beneficiary_category": ["SC", "ST", "OPEN"],
        "income_ceiling_annual": 800000,
        "benefit_description": "Annual stipend for vocational candidates",
        "max_amount": 50000,
        "eligible_course_types": ["ITI", "Polytechnic"],
        "application_portal_url": "https://mahadbt.maharashtra.gov.in",
        "deadline_date": "2028-06-30",
        "status": "active",
        "source": "OGD_DATAGOV_IN",
        "external_id": "ext-sch-test-ph12",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }

    created = create_scheme(scheme_data)
    assert created["scheme_code"] == "SCH-TEST-PH12"

    fetched = get_scheme("SCH-TEST-PH12")
    assert fetched is not None
    assert fetched["scheme_code"] == "SCH-TEST-PH12"

    fetched_by_id = get_scheme("77777777-7777-7777-7777-777777777777")
    assert fetched_by_id is not None
    assert fetched_by_id["scheme_code"] == "SCH-TEST-PH12"

    updated = update_scheme_repo("SCH-TEST-PH12", {"status": "closed"})
    assert updated["status"] == "closed"

    deleted = delete_scheme_repo("SCH-TEST-PH12")
    assert deleted is True

    fetched_after_delete = get_scheme("SCH-TEST-PH12")
    assert fetched_after_delete is None

    with pytest.raises(SchemeNotFoundError):
        update_scheme_repo("SCH-NONEXISTENT", {"status": "active"})


def test_gov_opportunity_provenance_preservation():
    official_data = {
        "id": "gov-prov-official-1",
        "name": "Official Drone Piloting Initiative",
        "department": "Civil Aviation",
        "description": "Certified drone pilot training",
        "status": "active",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_gov_opportunity(official_data)
    fetched_off = get_gov_opportunity("gov-prov-official-1")
    assert fetched_off["data_provenance"] == "GOVERNMENT_OFFICIAL"
    assert fetched_off["is_demo"] is False

    snapshot_data = {
        "id": "gov-prov-snapshot-1",
        "name": "Verified Snapshot CNC Machinist",
        "department": "Skill Development",
        "description": "Cached official curriculum",
        "status": "active",
        "source": "DATAGOV_IN",
        "data_provenance": "VERIFIED_SNAPSHOT",
        "is_demo": False,
    }
    create_gov_opportunity(snapshot_data)
    fetched_snap = get_gov_opportunity("gov-prov-snapshot-1")
    assert fetched_snap["data_provenance"] == "VERIFIED_SNAPSHOT"
    assert fetched_snap["data_provenance"] != "LIVE_API"
    assert fetched_snap["data_provenance"] != "DEMO_SYNTHETIC"

    demo_data = {
        "id": "gov-prov-demo-1",
        "name": "Demo Synthetic Automation",
        "department": "Simulation Lab",
        "description": "Demo record",
        "status": "active",
        "source": "DEMO_SYNTHETIC",
        "data_provenance": "DEMO_SYNTHETIC",
        "is_demo": True,
    }
    create_gov_opportunity(demo_data)
    fetched_demo = get_gov_opportunity("gov-prov-demo-1")
    assert fetched_demo["data_provenance"] == "DEMO_SYNTHETIC"
    assert fetched_demo["data_provenance"] != "GOVERNMENT_OFFICIAL"


def test_real_mode_demo_isolation():
    res_opps = client.get("/api/gov/opportunities?is_demo=false")
    assert res_opps.status_code == 200
    for opp in res_opps.json():
        assert opp.get("is_demo") is not True
        assert opp.get("source") != "DEMO_SYNTHETIC"
        assert opp.get("data_provenance") != "DEMO_SYNTHETIC"

    res_schemes = client.get("/api/schemes?is_demo=false")
    assert res_schemes.status_code == 200
    for sch in res_schemes.json():
        assert sch.get("is_demo") is not True
        assert sch.get("source") != "DEMO_SYNTHETIC"
        assert sch.get("data_provenance") != "DEMO_SYNTHETIC"

    res_demo_opp = client.get("/api/gov/opportunities/gov-prov-demo-1?is_demo=false")
    assert res_demo_opp.status_code == 404

    res_demo_sch = client.get("/api/schemes/sch-demo-001?is_demo=false")
    assert res_demo_sch.status_code == 404


def test_expired_records_filtered_from_recommendations():
    expired_opp = {
        "id": "gov-expired-opp-1",
        "name": "Expired EV Battery Maintenance Apprenticeship",
        "department": "Transport Dept",
        "description": "EV battery servicing program",
        "target_skills": ["Python", "Mechanical"],
        "district_coverage": ["State-wide (Maharashtra)"],
        "status": "active",
        "deadline": "2020-01-01",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    active_opp = {
        "id": "gov-future-opp-1",
        "name": "Active Modern EV Apprenticeship",
        "department": "Transport Dept",
        "description": "EV battery servicing program",
        "target_skills": ["Python", "Mechanical"],
        "district_coverage": ["State-wide (Maharashtra)"],
        "status": "active",
        "deadline": "2029-12-31",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_gov_opportunity(expired_opp)
    create_gov_opportunity(active_opp)

    res_rec = client.get("/api/gov/opportunities/recommended/stu-001")
    assert res_rec.status_code == 200
    rec_ids = [o["id"] for o in res_rec.json()["opportunities"]]
    assert "gov-expired-opp-1" not in rec_ids

    expired_scheme = {
        "id": "88888888-8888-8888-8888-888888888888",
        "scheme_code": "SCH-EXPIRED-2020",
        "title": "Expired Technology Grant Scheme",
        "department": "Skill Ministry",
        "scheme_type": "scholarship",
        "target_skills": ["Python"],
        "eligible_course_types": ["ITI", "Degree"],
        "status": "active",
        "deadline_date": "2020-05-15",
        "source": "OGD_DATAGOV_IN",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_scheme(expired_scheme)

    res_sch_rec = client.get("/api/schemes/recommended/stu-001")
    assert res_sch_rec.status_code == 200
    sch_codes = [s.get("scheme_code") for s in res_sch_rec.json()["schemes"]]
    assert "SCH-EXPIRED-2020" not in sch_codes


def test_rejected_records_filtered_from_recommendations():
    rejected_opp = {
        "id": "gov-rejected-opp-1",
        "name": "Rejected Welding Training Program",
        "department": "Heavy Industry",
        "description": "Unaccredited welding program",
        "target_skills": ["Python", "Mechanical"],
        "district_coverage": ["State-wide (Maharashtra)"],
        "status": "rejected",
        "verification_status": "REJECTED",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_gov_opportunity(rejected_opp)

    res_rec = client.get("/api/gov/opportunities/recommended/stu-001")
    assert res_rec.status_code == 200
    rec_ids = [o["id"] for o in res_rec.json()["opportunities"]]
    assert "gov-rejected-opp-1" not in rec_ids

    rejected_scheme = {
        "id": "99999999-9999-9999-9999-999999999999",
        "scheme_code": "SCH-REJECTED-001",
        "title": "Rejected Grant Scheme",
        "department": "Private Agency",
        "scheme_type": "scholarship",
        "target_skills": ["Python"],
        "eligible_course_types": ["Degree"],
        "status": "rejected",
        "verification_status": "REJECTED",
        "source": "OGD_DATAGOV_IN",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_scheme(rejected_scheme)

    res_sch_rec = client.get("/api/schemes/recommended/stu-001")
    assert res_sch_rec.status_code == 200
    sch_codes = [s.get("scheme_code") for s in res_sch_rec.json()["schemes"]]
    assert "SCH-REJECTED-001" not in sch_codes


def test_deterministic_deduplication_and_repeated_ingestion():
    batch_schemes = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "scheme_code": "SCH-DEDUP-001",
            "title": "Solar Subsidy v1",
            "department": "Energy",
            "scheme_type": "scholarship",
            "benefit_description": "Initial subsidy",
            "source": "OGD_DATAGOV_IN",
            "external_id": "ext-dedup-001",
            "status": "active",
        }
    ]
    upsert_schemes(batch_schemes)
    first_fetch = get_scheme("SCH-DEDUP-001")
    assert first_fetch is not None
    assert first_fetch["title"] == "Solar Subsidy v1"

    updated_batch = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "scheme_code": "SCH-DEDUP-001",
            "title": "Solar Subsidy v2",
            "department": "Energy",
            "scheme_type": "scholarship",
            "benefit_description": "Revised higher subsidy",
            "source": "OGD_DATAGOV_IN",
            "external_id": "ext-dedup-001",
            "status": "active",
        }
    ]
    upsert_schemes(updated_batch)
    second_fetch = get_scheme("SCH-DEDUP-001")
    assert second_fetch is not None
    assert second_fetch["title"] == "Solar Subsidy v2"

    batch_opps = [
        {
            "id": "gov-dedup-opp-1",
            "name": "Robotics Trainee Initial",
            "department": "Industry 4.0",
            "description": "Round 1",
            "status": "active",
            "source": "GOVERNMENT_OFFICIAL",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "is_demo": False,
        }
    ]
    upsert_gov_opportunities(batch_opps)
    first_opp = get_gov_opportunity("gov-dedup-opp-1")
    assert first_opp["name"] == "Robotics Trainee Initial"

    updated_opps = [
        {
            "id": "gov-dedup-opp-1",
            "name": "Robotics Trainee Updated",
            "department": "Industry 4.0",
            "description": "Round 2 Updated",
            "status": "active",
            "source": "GOVERNMENT_OFFICIAL",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "is_demo": False,
        }
    ]
    upsert_gov_opportunities(updated_opps)
    second_opp = get_gov_opportunity("gov-dedup-opp-1")
    assert second_opp["name"] == "Robotics Trainee Updated"


def test_supabase_failure_propagation_fail_closed():
    with patch("app.repositories.supabase_repository.list_gov_opportunities", side_effect=SupabaseRepositoryError("Database connection lost")):
        res_opps = client.get("/api/gov/opportunities?is_demo=false")
        assert res_opps.status_code == 503
        assert "temporarily unavailable" in res_opps.json()["detail"].lower()

        res_types = client.get("/api/gov/opportunities/types?is_demo=false")
        assert res_types.status_code == 503

        res_rec = client.get("/api/gov/opportunities/recommended/stu-001?is_demo=false")
        assert res_rec.status_code == 503

    with patch("app.repositories.supabase_repository.get_gov_opportunity", side_effect=SupabaseRepositoryError("DB read error")):
        res_get = client.get("/api/gov/opportunities/gov-some-id?is_demo=false")
        assert res_get.status_code == 503

    with patch("app.repositories.supabase_repository.list_schemes", side_effect=SupabaseRepositoryError("Schemes DB offline")):
        res_schemes = client.get("/api/schemes?is_demo=false")
        assert res_schemes.status_code == 503

        res_meta = client.get("/api/schemes/categories?is_demo=false")
        assert res_meta.status_code == 503

        res_sch_rec = client.get("/api/schemes/recommended/stu-001?is_demo=false")
        assert res_sch_rec.status_code == 503


def test_student_recommendations_user_isolation():
    from app.repositories.supabase_repository import upsert_student_profile

    profile_a = {
        "id": "usr-student-001",
        "user_id": "usr-student-001",
        "full_name": "Student Alpha",
        "preferred_location": "Pune",
        "skills": [{"name": "Python", "proficiency": "advanced"}],
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    upsert_student_profile(profile_a)

    unauth_opps = client.get("/api/gov/opportunities/recommended/usr-student-001")
    assert unauth_opps.status_code == 401

    unauth_sch = client.get("/api/schemes/recommended/usr-student-001")
    assert unauth_sch.status_code == 401

    token_b = create_access_token(data={"sub": "usr-student-002", "email": "student2@skillsetu.gov.in", "role": "STUDENT"})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    forbidden_opps = client.get("/api/gov/opportunities/recommended/usr-student-001", headers=headers_b)
    assert forbidden_opps.status_code == 403

    forbidden_sch = client.get("/api/schemes/recommended/usr-student-001", headers=headers_b)
    assert forbidden_sch.status_code == 403

    token_a = create_access_token(data={"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    allowed_opps = client.get("/api/gov/opportunities/recommended/usr-student-001", headers=headers_a)
    assert allowed_opps.status_code == 200
    assert allowed_opps.json()["student_id"] == "usr-student-001"

    allowed_sch = client.get("/api/schemes/recommended/usr-student-001", headers=headers_a)
    assert allowed_sch.status_code == 200
    assert allowed_sch.json()["student_id"] == "usr-student-001"


def test_admin_and_gov_rbac_protections():
    unauth_admin = client.get("/api/admin/gov/opportunities")
    assert unauth_admin.status_code == 401

    wrong_key_admin = client.get("/api/admin/gov/opportunities", headers={"X-Admin-Key": "wrong-key"})
    assert wrong_key_admin.status_code == 401

    valid_admin = client.get("/api/admin/gov/opportunities", headers={"X-Admin-Key": ADMIN_KEY})
    assert valid_admin.status_code == 200
    assert valid_admin.json()["status"] == "success"

    opp_payload = {
        "name": "Automated Drone Technician Scheme",
        "department": "Directorate of Vocational Education",
        "description": "Training in drone maintenance and flight ops",
        "opportunity_type": "APPRENTICESHIP",
        "district_coverage": "Pune",
        "status": "active",
    }

    student_token = create_access_token(data={"sub": "usr-student-001", "email": "student@skillsetu.gov.in", "role": "STUDENT"})
    student_res = client.post("/api/gov/opportunities", json=opp_payload, headers={"Authorization": f"Bearer {student_token}"})
    assert student_res.status_code == 403

    gov_token = create_access_token(data={"sub": "usr-gov-001", "email": "government@skillsetu.gov.in", "role": "GOVERNMENT"})
    gov_res = client.post("/api/gov/opportunities", json=opp_payload, headers={"Authorization": f"Bearer {gov_token}"})
    assert gov_res.status_code == 201
    assert gov_res.json()["status"] == "created"
    assert gov_res.json()["opportunity"]["data_provenance"] == "GOVERNMENT_OFFICIAL"

    admin_res = client.get("/api/admin/gov/opportunities", headers={"X-Admin-Key": ADMIN_KEY})
    assert admin_res.status_code == 200
    opps = admin_res.json()["opportunities"]
    assert any(o["name"] == "Automated Drone Technician Scheme" for o in opps)


def test_gov_opportunity_deduplication_and_upsert():
    gov_token = create_access_token(data={"sub": "usr-gov-001", "email": "government@skillsetu.gov.in", "role": "GOVERNMENT"})
    opp_v1 = {
        "name": "State Drone Operations Initiative",
        "department": "Aviation Skilling Council",
        "description": "Initial draft of drone pilot program",
        "opportunity_type": "APPRENTICESHIP",
        "status": "active",
        "district_coverage": "Pune",
    }
    res_1 = client.post("/api/gov/opportunities", json=opp_v1, headers={"Authorization": f"Bearer {gov_token}"})
    assert res_1.status_code == 201
    id_1 = res_1.json()["opportunity"]["id"]

    opp_v2 = {
        "name": "State Drone Operations Initiative",
        "department": "Aviation Skilling Council",
        "description": "Comprehensive updated drone pilot and payload operations syllabus",
        "opportunity_type": "APPRENTICESHIP",
        "status": "active",
        "district_coverage": "Pune, Mumbai City",
        "deadline": "2028-11-30",
    }
    res_2 = client.post("/api/gov/opportunities", json=opp_v2, headers={"Authorization": f"Bearer {gov_token}"})
    assert res_2.status_code == 201
    id_2 = res_2.json()["opportunity"]["id"]
    assert id_1 == id_2

    listing_res = client.get("/api/gov/opportunities?is_demo=false")
    assert listing_res.status_code == 200
    matched = [o for o in listing_res.json() if o.get("name") == "State Drone Operations Initiative"]
    assert len(matched) == 1
    assert "Comprehensive updated" in matched[0]["description"]

    admin_res = client.get("/api/admin/gov/opportunities", headers={"X-Admin-Key": ADMIN_KEY})
    assert admin_res.status_code == 200
    admin_matched = [o for o in admin_res.json()["opportunities"] if o.get("name") == "State Drone Operations Initiative"]
    assert len(admin_matched) == 1
    assert admin_matched[0]["id"] == id_1


def test_industry_signals_real_external_ingestion_and_provenance():
    from unittest.mock import patch, MagicMock
    from app.ingestion.industry_intelligence import industry_ingestor

    sample_rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Python PEPs</title>
        <link>https://peps.python.org</link>
        <description>Python Enhancement Proposals</description>
        <item>
          <title>PEP 999: Advanced Type Inference for Data Systems</title>
          <link>https://peps.python.org/pep-0999/</link>
          <description>Formal specification of static type analysis and high performance async pipelines.</description>
          <pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = sample_rss_xml

    with patch("app.ingestion.industry_intelligence.httpx.get", return_value=fake_resp):
        items = industry_ingestor.fetch_external_feeds()
        assert len(items) >= 1
        first = items[0]
        assert first["data_provenance"] == "VERIFIED_EXTERNAL_FEED"
        assert first["is_demo"] is False
        assert first["validation_status"] == "APPROVED"
        assert first["source_type"] == "TECH_DOCUMENTATION"
        assert "Python" in first["skills"]

    with patch.object(industry_ingestor, "fetch_external_feeds", return_value=items):
        summary = industry_ingestor.ingest_from_feeds(is_demo=False)
        assert summary["status"] == "success"
        assert summary["records_fetched"] >= 1
        assert summary["records_added"] + summary["records_updated"] >= 1

    unverified_payload = {
        "title": "Unverified Community Tech Article",
        "description": "Informal overview of web frameworks without verified editorial lineage.",
        "category": "NEW_TECHNOLOGY",
        "industry": "Software",
        "skills": ["Web Development"],
        "source_url": "https://random-tech-blog.example.com/post-1",
        "source_name": "Random Tech Blog",
        "data_provenance": "UNVERIFIED_EXTERNAL_SOURCE",
    }
    norm, err = industry_ingestor.validate_and_normalize(unverified_payload, is_demo=False)
    assert err is None
    assert norm["data_provenance"] == "UNVERIFIED_EXTERNAL_SOURCE"
    assert norm["validation_status"] == "PENDING"
    assert norm["is_active"] is False


def test_industry_signals_all_sources_failed_reports_failure():
    from unittest.mock import patch, MagicMock
    from app.ingestion.industry_intelligence import industry_ingestor

    fake_err_resp = MagicMock()
    fake_err_resp.status_code = 503

    with patch("app.ingestion.industry_intelligence.httpx.get", return_value=fake_err_resp):
        summary = industry_ingestor.ingest_from_feeds(is_demo=False)
        assert summary["status"] == "FAILED"
        assert len(summary["errors"]) >= 1


def test_industry_signals_missing_pubdate_becomes_pending_and_unverified():
    from unittest.mock import patch, MagicMock
    from app.ingestion.industry_intelligence import industry_ingestor

    xml_no_pubdate = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Python PEPs</title>
        <link>https://peps.python.org</link>
        <item>
          <title>PEP 1000: Quantum Typing System</title>
          <link>https://peps.python.org/pep-1000/</link>
          <description>Quantum typing specifications for next-gen runtime.</description>
        </item>
      </channel>
    </rss>"""

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = xml_no_pubdate

    with patch("app.ingestion.industry_intelligence.httpx.get", return_value=fake_resp):
        items = industry_ingestor.fetch_external_feeds()
        assert len(items) >= 1
        item = items[0]
        assert item["validation_status"] == "PENDING"
        assert item["is_active"] is False
        assert item["data_provenance"] == "UNVERIFIED_EXTERNAL_SOURCE"
        assert item["published_at"] is None


def test_industry_signals_existing_signal_update_propagates_trust_fields():
    from app.ingestion.industry_intelligence import industry_ingestor
    from app.db import save_industry_signal, get_industry_signal_by_id

    initial_sig = {
        "id": "ind-sig-trust-test-1",
        "title": "Autonomous Robotics Framework",
        "description": "Initial draft robotics framework",
        "category": "TOOL_RELEASE",
        "industry": "Robotics",
        "skills": ["Robotics"],
        "tools": ["ROS"],
        "source_url": "https://robotics.example.com/v1",
        "source_name": "Robotics Org",
        "source_type": "TECH_DOCUMENTATION",
        "data_provenance": "UNVERIFIED_EXTERNAL_SOURCE",
        "validation_status": "PENDING",
        "is_active": False,
        "is_demo": False,
    }
    save_industry_signal(initial_sig)

    verified_update = [
        {
            "id": "ind-sig-trust-test-1",
            "title": "Autonomous Robotics Framework",
            "description": "Updated approved robotics framework specifications",
            "category": "TOOL_RELEASE",
            "industry": "Robotics",
            "skills": ["Robotics", "ROS 2"],
            "tools": ["ROS", "Gazebo"],
            "source_url": "https://robotics.example.com/v1",
            "source_name": "Robotics Org",
            "source_type": "TECH_DOCUMENTATION",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "validation_status": "APPROVED",
            "is_active": True,
            "is_demo": False,
            "published_at": "2026-09-17T00:00:00Z",
        }
    ]

    summary = industry_ingestor.ingest_from_feeds(feeds=verified_update, is_demo=False)
    assert summary["records_updated"] >= 1

    updated_rec = get_industry_signal_by_id("ind-sig-trust-test-1")
    assert updated_rec is not None
    assert updated_rec["data_provenance"] == "VERIFIED_EXTERNAL_FEED"
    assert updated_rec["validation_status"] == "APPROVED"
    assert updated_rec["is_active"] is True


def test_admin_update_gov_opportunity_not_found_returns_404():
    res = client.patch(
        "/api/admin/gov/opportunities/gov-missing-id-9999",
        json={"status": "inactive"},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    assert res.status_code == 404


def test_rejected_scheme_excluded_from_listing_and_detail():
    scheme_data = {
        "id": "55555555-5555-5555-5555-555555555555",
        "scheme_code": "SCH-REJ-TEST-12",
        "title": "Rejected Grant Scheme Detail",
        "department": "Higher Education",
        "scheme_type": "scholarship",
        "benefit_description": "Grant for students",
        "status": "rejected",
        "verification_status": "REJECTED",
        "source": "OGD_DATAGOV_IN",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    create_scheme(scheme_data)

    res_list = client.get("/api/schemes?is_demo=false")
    assert res_list.status_code == 200
    matched_codes = [s.get("scheme_code") for s in res_list.json()]
    assert "SCH-REJ-TEST-12" not in matched_codes

    res_detail = client.get("/api/schemes/SCH-REJ-TEST-12?is_demo=false")
    assert res_detail.status_code == 404


def test_gov_opportunity_district_pagination_filtering():
    for i in range(15):
        opp = {
            "id": f"gov-dist-pune-{i}",
            "name": f"Pune Trainee Skill Opportunity {i}",
            "department": "Technical Education",
            "description": f"Training course number {i}",
            "district_coverage": ["Pune"],
            "opportunity_type": "APPRENTICESHIP",
            "status": "active",
            "source": "GOVERNMENT_OFFICIAL",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "is_demo": False,
        }
        create_gov_opportunity(opp)

    paged = list_gov_opportunities(district="Pune", limit=5, offset=2)
    assert len(paged) == 5
