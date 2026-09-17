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


def test_gov_opportunity_deterministic_128bit_id_and_consistency():
    from app.repositories.supabase_repository import generate_gov_opportunity_id

    expected_id = generate_gov_opportunity_id("Solar Energy Trainee Program", "Department of Renewable Energy")
    assert expected_id.startswith("gov-")
    assert len(expected_id) == 36

    opp_data = {
        "name": "Solar Energy Trainee Program",
        "department": "Department of Renewable Energy",
        "description": "Comprehensive solar technician training course",
        "status": "active",
        "source": "GOVERNMENT_OFFICIAL",
        "data_provenance": "GOVERNMENT_OFFICIAL",
        "is_demo": False,
    }
    repo_created = create_gov_opportunity(dict(opp_data))
    assert repo_created["id"] == expected_id

    batch_created = upsert_gov_opportunities([dict(opp_data)])
    assert len(batch_created) == 1
    assert batch_created[0]["id"] == expected_id

    admin_opp = {
        "name": "Solar Energy Trainee Program",
        "department": "Department of Renewable Energy",
        "description": "Comprehensive solar technician training course",
        "status": "active",
    }
    res_admin = client.post(
        "/api/admin/gov/opportunities",
        headers={"X-Admin-Key": ADMIN_KEY},
        json=admin_opp,
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["opportunity"]["id"] == expected_id


def test_trigger_admin_industry_ingestion_async_behavior():
    import asyncio
    from app.ingestion.industry_intelligence import industry_ingestor

    custom_feed = [
        {
            "id": "ind-sig-async-test-1",
            "title": "Async Event-Loop Processing Engine",
            "description": "High performance async event loop worker runtime",
            "category": "TOOL_RELEASE",
            "industry": "Software Engineering",
            "skills": ["Async Programming", "Python"],
            "tools": ["asyncio"],
            "source_url": "https://python.org/async-engine",
            "source_name": "Python Foundation",
            "source_type": "TECH_DOCUMENTATION",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "validation_status": "APPROVED",
            "is_active": True,
            "is_demo": False,
            "published_at": "2026-09-17T12:00:00Z",
        }
    ]

    direct_async_res = asyncio.run(industry_ingestor.async_ingest_from_feeds(feeds=custom_feed, is_demo=False))
    assert direct_async_res["records_added"] >= 1 or direct_async_res["records_updated"] >= 1

    api_res = client.post(
        "/api/admin/industry/ingest",
        headers={"X-Admin-Key": ADMIN_KEY},
        json=custom_feed,
    )
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["status"] == "success"
    assert "summary" in data
    assert data["summary"]["records_added"] + data["summary"]["records_updated"] + data["summary"]["records_duplicated"] >= 1


def test_generate_gov_opportunity_id_prevents_delimiter_collisions():
    from app.repositories.supabase_repository import generate_gov_opportunity_id

    id1 = generate_gov_opportunity_id("solar|energy", "renewables")
    id2 = generate_gov_opportunity_id("solar", "energy|renewables")
    assert id1 != id2
    assert id1.startswith("gov-")
    assert id2.startswith("gov-")
    assert len(id1) == 36
    assert len(id2) == 36


def test_industry_signals_duplicate_update_persists_and_preserves_published_at():
    from app.ingestion.industry_intelligence import industry_ingestor
    from app.db import save_industry_signal, get_industry_signal_by_id

    sig_id = "ind-sig-pubdate-test-1"
    initial_sig = {
        "id": sig_id,
        "title": "Quantum Operating Architecture",
        "description": "Initial draft quantum kernel",
        "category": "TOOL_RELEASE",
        "industry": "Computing",
        "skills": ["Quantum"],
        "tools": ["Qiskit"],
        "source_url": "https://quantum.example.com/v1",
        "source_name": "Quantum Foundation",
        "source_type": "TECH_DOCUMENTATION",
        "data_provenance": "UNVERIFIED_EXTERNAL_SOURCE",
        "validation_status": "PENDING",
        "is_active": False,
        "is_demo": False,
        "published_at": None,
    }
    save_industry_signal(initial_sig)

    verified_update = [
        {
            "id": sig_id,
            "title": "Quantum Operating Architecture",
            "description": "Updated approved quantum kernel specifications",
            "category": "TOOL_RELEASE",
            "industry": "Computing",
            "skills": ["Quantum"],
            "tools": ["Qiskit"],
            "source_url": "https://quantum.example.com/v1",
            "source_name": "Quantum Foundation",
            "source_type": "TECH_DOCUMENTATION",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "validation_status": "APPROVED",
            "is_active": True,
            "is_demo": False,
            "published_at": "2026-09-17T08:30:00Z",
        }
    ]
    summary1 = industry_ingestor.ingest_from_feeds(feeds=verified_update, is_demo=False)
    assert summary1["records_updated"] >= 1

    rec1 = get_industry_signal_by_id(sig_id)
    assert rec1 is not None
    assert rec1["published_at"] == "2026-09-17T08:30:00Z"

    no_date_update = [
        {
            "id": sig_id,
            "title": "Quantum Operating Architecture",
            "description": "Second update without published_at field",
            "category": "TOOL_RELEASE",
            "industry": "Computing",
            "skills": ["Quantum"],
            "tools": ["Qiskit"],
            "source_url": "https://quantum.example.com/v1",
            "source_name": "Quantum Foundation",
            "source_type": "TECH_DOCUMENTATION",
            "data_provenance": "VERIFIED_EXTERNAL_FEED",
            "validation_status": "APPROVED",
            "is_active": True,
            "is_demo": False,
            "published_at": None,
        }
    ]
    summary2 = industry_ingestor.ingest_from_feeds(feeds=no_date_update, is_demo=False)
    assert summary2["records_updated"] >= 1

    rec2 = get_industry_signal_by_id(sig_id)
    assert rec2 is not None
    assert rec2["published_at"] == "2026-09-17T08:30:00Z"


def test_trigger_admin_industry_ingestion_failure_mapping():
    from unittest.mock import patch, MagicMock

    fake_err_resp = MagicMock()
    fake_err_resp.status_code = 503

    with patch("app.ingestion.industry_intelligence.httpx.get", return_value=fake_err_resp):
        res = client.post(
            "/api/admin/industry/ingest",
            headers={"X-Admin-Key": ADMIN_KEY},
            json=None,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "failed"
        assert "failed" in data["message"].lower()
        assert data["summary"]["status"] == "FAILED"
        assert len(data["summary"]["errors"]) >= 1


def test_reconcile_gov_opportunities_legacy_id_to_canonical():
    from app.repositories.supabase_repository import reconcile_gov_opportunities, generate_gov_opportunity_id

    legacy_records = [
        {
            "id": "gov-1405fff7",
            "name": "Maharashtra Green Hydrogen Apprenticeship Scheme 2026",
            "department": "Department of Skills & Renewable Energy",
            "description": "Comprehensive statewide training in green hydrogen safety.",
            "target_skills": ["Hydrogen Safety"],
            "district_coverage": ["Pune"],
            "status": "active",
            "source": "USER_SUBMITTED",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "is_demo": False,
        }
    ]
    survivors, stats = reconcile_gov_opportunities(legacy_records)
    expected_cid = generate_gov_opportunity_id(
        "Maharashtra Green Hydrogen Apprenticeship Scheme 2026",
        "Department of Skills & Renewable Energy",
    )
    assert len(survivors) == 1
    assert survivors[0]["id"] == expected_cid
    assert stats["updated_ids"] == 1
    assert stats["merged_duplicates"] == 0


def test_reconcile_gov_opportunities_duplicate_collision_and_deterministic_survivor():
    from app.repositories.supabase_repository import reconcile_gov_opportunities, generate_gov_opportunity_id

    opp_name = "Solar Rooftop Technical Installation"
    opp_dept = "Energy Department"
    expected_cid = generate_gov_opportunity_id(opp_name, opp_dept)

    duplicates = [
        {
            "id": "gov-legacy-01",
            "name": "  solar rooftop technical installation  ",
            "department": "  energy department ",
            "description": "",
            "eligibility_criteria": "Diploma in Electrical",
            "target_skills": ["Solar PV"],
            "district_coverage": ["Nagpur"],
            "status": "inactive",
            "data_provenance": "USER_SUBMITTED",
            "verification_status": "PENDING",
            "is_demo": False,
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-02T00:00:00Z",
        },
        {
            "id": "gov-legacy-02",
            "name": "Solar Rooftop Technical Installation",
            "department": "Energy Department",
            "description": "Official technical apprentice training program",
            "eligibility_criteria": "",
            "target_skills": ["Inverter Maintenance"],
            "district_coverage": ["Pune", "Nashik"],
            "status": "active",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "verification_status": "VERIFIED",
            "is_demo": False,
            "created_at": "2026-09-05T00:00:00Z",
            "updated_at": "2026-09-10T00:00:00Z",
        },
        {
            "id": "gov-legacy-03",
            "name": "Solar Rooftop Technical Installation",
            "department": "Energy Department",
            "description": "Demo duplicate",
            "target_skills": ["Solar PV"],
            "district_coverage": ["Mumbai"],
            "status": "active",
            "data_provenance": "DEMO_SYNTHETIC",
            "verification_status": "PENDING",
            "is_demo": True,
            "created_at": "2026-09-03T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
        },
    ]

    survivors, stats = reconcile_gov_opportunities(duplicates)
    assert len(survivors) == 1
    assert stats["merged_duplicates"] == 2
    assert stats["updated_ids"] == 1

    survivor = survivors[0]
    assert survivor["id"] == expected_cid
    assert survivor["data_provenance"] == "GOVERNMENT_OFFICIAL"
    assert survivor["verification_status"] == "VERIFIED"
    assert survivor["status"] == "active"
    assert survivor["is_demo"] is False
    assert survivor["description"] == "Official technical apprentice training program"
    assert survivor["eligibility_criteria"] == "Diploma in Electrical"
    assert set(survivor["target_skills"]) == {"Inverter Maintenance", "Solar PV"}
    assert set(survivor["district_coverage"]) == {"Pune", "Nashik", "Nagpur", "Mumbai"}


def test_reconcile_gov_opportunities_idempotency():
    from app.repositories.supabase_repository import reconcile_gov_opportunities

    records = [
        {
            "id": "gov-legacy-x1",
            "name": "Cybersecurity SOC Trainee",
            "department": "IT & Telecom",
            "status": "active",
            "data_provenance": "GOVERNMENT_OFFICIAL",
            "is_demo": False,
        },
        {
            "id": "gov-legacy-x2",
            "name": "cybersecurity soc trainee",
            "department": "it & telecom",
            "status": "pending",
            "data_provenance": "USER_SUBMITTED",
            "is_demo": False,
        },
    ]

    run1, stats1 = reconcile_gov_opportunities(records)
    assert len(run1) == 1
    assert stats1["merged_duplicates"] == 1

    run2, stats2 = reconcile_gov_opportunities(run1)
    assert len(run2) == 1
    assert run2 == run1
    assert stats2["merged_duplicates"] == 0
    assert stats2["updated_ids"] == 0


def test_create_upsert_cannot_recreate_duplicate_canonical_opportunity():
    from app.repositories.supabase_repository import generate_gov_opportunity_id
    from app.db import save_gov_opportunity

    opp_data = {
        "name": "Statewide Precision Agriculture Training",
        "department": "Agriculture & Rural Development",
        "description": "Smart farming and drone piloting training",
        "district_coverage": ["Satara", "Kolhapur"],
        "status": "active",
    }
    saved1 = save_gov_opportunity(dict(opp_data))
    cid1 = saved1["id"]
    expected_cid = generate_gov_opportunity_id(opp_data["name"], opp_data["department"])
    assert cid1 == expected_cid

    updated_data = {
        "name": "  statewide precision agriculture training  ",
        "department": " agriculture & rural development ",
        "description": "Updated training program description",
        "district_coverage": ["Satara", "Kolhapur", "Solapur"],
        "status": "active",
    }
    saved2 = save_gov_opportunity(dict(updated_data))
    cid2 = saved2["id"]
    assert cid2 == expected_cid

    from app.db import _cache
    cached_matches = [
        o for o in _cache.get("gov_opportunities", [])
        if o.get("id") == expected_cid
    ]
    assert len(cached_matches) == 1
    assert cached_matches[0]["description"] == "Updated training program description"


def test_sql_migration_file_exists_and_valid():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    mig_file = repo_root / "data" / "migrations" / "20260917_reconcile_gov_opportunity_canonical_ids.sql"
    assert mig_file.exists()
    content = mig_file.read_text(encoding="utf-8")
    assert "canonical_gov_opportunity_id" in content
    assert "idx_gov_opportunities_canonical_key" in content
    assert "sha256" in content
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in content
    assert "WHERE name IS NOT NULL AND trim(name) <> ''" in content


def test_save_gov_opportunity_multiple_cache_matches_dedup():
    from app.db import _cache, save_gov_opportunity
    from app.repositories.supabase_repository import generate_gov_opportunity_id

    records = _cache.setdefault("gov_opportunities", [])
    test_name = "Precision Drone Inspection Fellowship"
    test_dept = "Civil Aviation"
    canonical_id = generate_gov_opportunity_id(test_name, test_dept)

    records.insert(0, {
        "id": "unrelated-gov-1",
        "name": "Unrelated Opportunity",
        "department": "Other Dept",
        "description": "Keep me",
        "status": "active",
        "is_demo": False,
    })
    records.insert(1, {
        "id": "legacy-id-dup-1",
        "name": "precision drone inspection fellowship",
        "department": "civil aviation",
        "description": "Legacy duplicate 1",
        "status": "active",
        "is_demo": False,
    })
    records.insert(2, {
        "id": "middle-unrelated",
        "name": "Middle Unrelated",
        "department": "Other Dept",
        "description": "Keep me too",
        "status": "active",
        "is_demo": False,
    })
    records.insert(3, {
        "id": canonical_id,
        "name": test_name,
        "department": test_dept,
        "description": "Legacy duplicate 2",
        "status": "pending",
        "is_demo": False,
    })

    incoming = {
        "name": test_name,
        "department": test_dept,
        "description": "Authoritative merged description",
        "district_coverage": ["Pune"],
        "status": "active",
    }
    saved = save_gov_opportunity(incoming)
    assert saved["id"] == canonical_id
    assert saved["description"] == "Authoritative merged description"

    matching_in_cache = [r for r in records if r.get("id") == canonical_id]
    assert len(matching_in_cache) == 1
    assert matching_in_cache[0]["description"] == "Authoritative merged description"

    name_matches = [
        r for r in records
        if (r.get("name") or "").strip().lower() == test_name.lower()
        and (r.get("department") or "").strip().lower() == test_dept.lower()
    ]
    assert len(name_matches) == 1

    assert any(r.get("id") == "unrelated-gov-1" for r in records)
    assert any(r.get("id") == "middle-unrelated" for r in records)
    assert not any(r.get("id") == "legacy-id-dup-1" for r in records)


def test_update_gov_opportunity_repo_name_department_and_canonical_id():
    from app.repositories.supabase_repository import (
        create_gov_opportunity,
        get_gov_opportunity,
        update_gov_opportunity_repo,
        generate_gov_opportunity_id,
        GovOpportunityNotFoundError,
    )

    initial_name = "Automated Warehousing Apprenticeship"
    initial_dept = "Logistics Council"
    initial_id = generate_gov_opportunity_id(initial_name, initial_dept)

    opp = create_gov_opportunity({
        "id": initial_id,
        "name": initial_name,
        "department": initial_dept,
        "description": "Warehousing logistics tech training",
        "status": "active",
        "target_skills": ["Supply Chain", "Automation"],
        "is_demo": False,
    })
    assert opp["id"] == initial_id

    new_name = "Smart Robotics Warehousing Apprenticeship"
    new_id = generate_gov_opportunity_id(new_name, initial_dept)
    assert new_id != initial_id

    updated = update_gov_opportunity_repo(initial_id, {
        "name": new_name,
        "description": "Updated logistics curriculum",
    })
    assert updated["id"] == new_id
    assert updated["name"] == new_name
    assert updated["department"] == initial_dept
    assert updated["description"] == "Updated logistics curriculum"
    assert updated["status"] == "active"
    assert updated["target_skills"] == ["Supply Chain", "Automation"]

    assert get_gov_opportunity(initial_id) is None
    new_fetched = get_gov_opportunity(new_id)
    assert new_fetched is not None
    assert new_fetched["name"] == new_name

    non_key_updated = update_gov_opportunity_repo(new_id, {"status": "inactive"})
    assert non_key_updated["id"] == new_id
    assert non_key_updated["status"] == "inactive"
    assert non_key_updated["name"] == new_name

    with pytest.raises(GovOpportunityNotFoundError):
        update_gov_opportunity_repo("gov-completely-absent-id", {"name": "Nonexistent"})
