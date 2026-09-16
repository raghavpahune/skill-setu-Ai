"""Phase 32D Test Suite: Supabase System-of-Record Foundation for courses.

Verifies:
1. Repository course lifecycle (get, list, create, update, delete).
2. Supabase reads bypass stale local cache.
3. Supabase writes persist directly to Supabase.
4. Supabase failure (insert, update, delete, select) returns HTTP 5xx.
5. Zero fallback to local JSON/cache on Supabase database failure.
6. Institute ownership / RBAC enforcement.
7. Admin authorization across courses.
8. Unauthorized student mutation rejected with 403.
9. Cross-institute mutation strictly rejected with 403.
10. Missing course records return 404.
11. Downstream intelligence/curriculum services read Supabase courses.
12. Phase 32A, 32B, and 32C workflows remain fully functional.
"""
import uuid
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.repositories.supabase_repository import (
    get_course,
    list_courses,
    create_course,
    update_course_repo,
    delete_course_repo,
    CourseNotFoundError,
    SupabaseRepositoryError,
    get_client,
)
from app.db import _cache, init_db, init_demo_users, save_user

init_db()
init_demo_users()

client = TestClient(app)

# Ensure secondary institute and student demo users exist in auth store
save_user({
    "id": "usr-institute-002",
    "email": "institute2@skillsetu.gov.in",
    "role": "INSTITUTE",
    "organization_id": "inst-vjti",
    "full_name": "VJTI Principal",
    "hashed_password": hash_password("Password@123"),
})
save_user({
    "id": "usr-student-p32d",
    "email": "student_p32d@skillsetu.gov.in",
    "role": "STUDENT",
    "full_name": "Student Tester",
    "hashed_password": hash_password("Password@123"),
})

INSTITUTE_1_TOKEN = create_access_token({
    "sub": "usr-institute-001",
    "email": "institute@skillsetu.gov.in",
    "role": "INSTITUTE",
    "organization_id": "inst-coep",
})
INSTITUTE_1_HEADERS = {"Authorization": f"Bearer {INSTITUTE_1_TOKEN}"}

INSTITUTE_2_TOKEN = create_access_token({
    "sub": "usr-institute-002",
    "email": "institute2@skillsetu.gov.in",
    "role": "INSTITUTE",
    "organization_id": "inst-vjti",
})
INSTITUTE_2_HEADERS = {"Authorization": f"Bearer {INSTITUTE_2_TOKEN}"}

STUDENT_TOKEN = create_access_token({
    "sub": "usr-student-p32d",
    "email": "student_p32d@skillsetu.gov.in",
    "role": "STUDENT",
})
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}

ADMIN_TOKEN = create_access_token({
    "sub": "usr-admin-001",
    "email": "admin@skillsetu.gov.in",
    "role": "ADMIN",
})
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def test_01_repository_course_lifecycle():
    """Verify get_course, list_courses, create_course, update_course_repo, delete_course_repo."""
    cid = f"cr-test-{uuid.uuid4().hex[:8]}"
    course_data = {
        "id": cid,
        "course_id": cid,
        "name": "Robotics & Micro-controllers",
        "institute": "COEP Pune",
        "district": "Pune",
        "category": "Robotics",
        "skills": ["Robotics", "Embedded C"],
        "enrolment_count": 45,
        "source": "USER_SUBMITTED",
        "is_demo": False,
        "status": "active",
    }

    # 1. Create
    created = create_course(course_data)
    assert created["id"] == cid
    assert created["name"] == "Robotics & Micro-controllers"

    # 2. Get
    fetched = get_course(cid)
    assert fetched is not None
    assert fetched["id"] == cid
    assert fetched["district"] == "Pune"

    # 3. List
    courses = list_courses(category="Robotics")
    assert any(c["id"] == cid for c in courses)

    # 4. Update
    updated = update_course_repo(cid, {"enrolment_count": 60, "status": "review_oversupply"})
    assert updated["enrolment_count"] == 60
    assert updated["status"] == "review_oversupply"

    refetched = get_course(cid)
    assert refetched["enrolment_count"] == 60

    # 5. Delete
    deleted = delete_course_repo(cid)
    assert deleted is True
    assert get_course(cid) is None


def test_02_api_courses_bypasses_stale_cache():
    """Verify API reads directly from Supabase courses table, bypassing local cache."""
    cid = f"cr-supabase-{uuid.uuid4().hex[:8]}"
    course_row = {
        "id": cid,
        "name": "Cloud Native Kubernetes Engineering",
        "institute": "Pune Institute",
        "district": "Pune",
        "category": "Cloud Computing",
        "enrolment_count": 50,
        "skills": ["Kubernetes", "Docker", "DevOps"],
        "status": "active",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }

    # Inject into Supabase mock directly
    mock_client = get_client()
    mock_client.table("courses").insert(course_row).execute()

    # Clear local cache courses
    _cache["courses"] = [{"id": "stale-cached-course", "name": "Stale Course"}]

    # 1. Test GET /api/courses
    resp = client.get("/api/courses")
    assert resp.status_code == 200
    ids = [c.get("id") for c in resp.json()]
    assert cid in ids

    # 2. Test GET /api/institute/courses
    resp_inst = client.get("/api/institute/courses")
    assert resp_inst.status_code == 200
    inst_ids = [c.get("id") for c in resp_inst.json()]
    assert cid in inst_ids


def test_03_api_post_course_persists_to_supabase():
    """Verify POST /api/institute/courses persists authoritatively to Supabase."""
    payload = {
        "name": "Autonomous Drone Navigation",
        "district": "Pune",
        "category": "Aerospace",
        "description": "Comprehensive drone flight controller & ROS syllabus",
        "skills": ["ROS", "Drone Avionics", "Python"],
        "enrolment_capacity": 40,
        "placed_count": 32,
        "duration_weeks": 16,
        "nsqf_level": 6,
        "status": "active",
    }

    resp = client.post("/api/institute/courses", json=payload, headers=INSTITUTE_1_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    course = data["course"]
    cid = course["id"]
    assert cid.startswith("cr-inst-")
    assert course["placement_rate"] == 80
    assert course["user_id"] == "usr-institute-001"
    assert course["institute_id"] == "inst-coep"

    # Confirm directly in Supabase table
    mock_client = get_client()
    sb_res = mock_client.table("courses").select("*").eq("id", cid).execute()
    assert len(sb_res.data) == 1
    assert sb_res.data[0]["name"] == "Autonomous Drone Navigation"


def test_04_api_patch_course_persists_to_supabase():
    """Verify PATCH /api/institute/courses/{course_id} updates directly in Supabase."""
    cid = f"cr-patch-{uuid.uuid4().hex[:8]}"
    initial_row = {
        "id": cid,
        "name": "Industrial IoT & Edge Computing",
        "institute": "COEP",
        "district": "Pune",
        "category": "IoT",
        "enrolment_count": 30,
        "placed_count": 15,
        "user_id": "usr-institute-001",
        "institute_id": "inst-coep",
        "status": "active",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    mock_client = get_client()
    mock_client.table("courses").insert(initial_row).execute()

    patch_payload = {
        "enrolment_capacity": 50,
        "placed_count": 40,
        "status": "active",
    }

    resp = client.patch(f"/api/institute/courses/{cid}", json=patch_payload, headers=INSTITUTE_1_HEADERS)
    assert resp.status_code == 200
    updated_course = resp.json()["course"]
    assert updated_course["enrolment_count"] == 50
    assert updated_course["placement_rate"] == 80

    # Verify directly from Supabase
    sb_course = get_course(cid)
    assert sb_course["enrolment_count"] == 50
    assert sb_course["placement_rate"] == 80


def test_05_supabase_failure_returns_5xx():
    """Verify that Supabase failure on courses operations raises HTTP 500 without local recovery."""
    mock_client = get_client()
    table = mock_client.table("courses")

    # 1. Insert failure
    table.should_fail_insert = True
    payload = {
        "name": "Failed Course Insertion",
        "district": "Pune",
        "category": "Tech",
        "skills": ["Python"],
        "enrolment_capacity": 30,
        "placed_count": 10,
    }
    resp = client.post("/api/institute/courses", json=payload, headers=INSTITUTE_1_HEADERS)
    assert resp.status_code == 500
    table.should_fail_insert = False

    # 2. Select failure
    table.should_fail_select = True
    resp_get = client.get("/api/courses")
    assert resp_get.status_code == 500

    resp_inst_get = client.get("/api/institute/courses")
    assert resp_inst_get.status_code == 500
    table.should_fail_select = False

    # 3. Update failure
    cid = f"cr-fail-upd-{uuid.uuid4().hex[:8]}"
    mock_client.table("courses").insert({
        "id": cid,
        "name": "Update Failure Test",
        "user_id": "usr-institute-001",
        "institute_id": "inst-coep",
    }).execute()

    table.should_fail_update = True
    resp_patch = client.patch(f"/api/institute/courses/{cid}", json={"enrolment_capacity": 60}, headers=INSTITUTE_1_HEADERS)
    assert resp_patch.status_code == 500
    table.should_fail_update = False

    # 4. Delete failure
    table.should_fail_delete = True
    resp_del = client.delete(f"/api/institute/courses/{cid}", headers=INSTITUTE_1_HEADERS)
    assert resp_del.status_code == 500
    table.should_fail_delete = False


def test_06_unauthenticated_requests_return_401():
    """Verify mutating courses without JWT auth token returns 401."""
    resp_post = client.post("/api/institute/courses", json={"name": "Test", "district": "Pune", "skills": ["AI"]})
    assert resp_post.status_code == 401

    resp_patch = client.patch("/api/institute/courses/cr-001", json={"name": "Test"})
    assert resp_patch.status_code == 401

    resp_del = client.delete("/api/institute/courses/cr-001")
    assert resp_del.status_code == 401


def test_07_student_mutation_rejected_with_403():
    """Verify student role attempting to create, patch, or delete courses receives 403 Forbidden."""
    payload = {
        "name": "Student Illicit Course",
        "district": "Pune",
        "skills": ["Coding"],
        "category": "Tech",
        "enrolment_capacity": 20,
    }
    # 1. Create
    resp_post = client.post("/api/institute/courses", json=payload, headers=STUDENT_HEADERS)
    assert resp_post.status_code == 403

    # 2. Patch
    resp_patch = client.patch("/api/institute/courses/cr-001", json={"name": "Tampered"}, headers=STUDENT_HEADERS)
    assert resp_patch.status_code == 403

    # 3. Delete
    resp_del = client.delete("/api/institute/courses/cr-001", headers=STUDENT_HEADERS)
    assert resp_del.status_code == 403


def test_08_cross_institute_mutation_rejected_with_403():
    """Verify Institute 2 cannot modify or delete Institute 1's courses."""
    cid = f"cr-inst1-{uuid.uuid4().hex[:8]}"
    course_data = {
        "id": cid,
        "name": "COEP Exclusive Workshop",
        "institute": "COEP Pune",
        "district": "Pune",
        "category": "Automotive",
        "enrolment_count": 40,
        "user_id": "usr-institute-001",
        "institute_id": "inst-coep",
        "user_email": "institute@skillsetu.gov.in",
        "status": "active",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    get_client().table("courses").insert(course_data).execute()

    # Institute 2 attempts to patch Institute 1's course
    resp_patch = client.patch(
        f"/api/institute/courses/{cid}",
        json={"name": "VJTI Hijacked Name"},
        headers=INSTITUTE_2_HEADERS,
    )
    assert resp_patch.status_code == 403

    # Institute 2 attempts to delete Institute 1's course
    resp_del = client.delete(
        f"/api/institute/courses/{cid}",
        headers=INSTITUTE_2_HEADERS,
    )
    assert resp_del.status_code == 403


def test_09_admin_can_update_and_delete_across_institutes():
    """Verify Admin can update and delete courses across all institutes."""
    cid = f"cr-admin-mgmt-{uuid.uuid4().hex[:8]}"
    course_data = {
        "id": cid,
        "name": "State Poly Advanced Solar Trade",
        "institute": "Government ITI Solapur",
        "district": "Solapur",
        "category": "Solar",
        "enrolment_count": 35,
        "user_id": "usr-institute-001",
        "institute_id": "inst-coep",
        "status": "active",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    get_client().table("courses").insert(course_data).execute()

    # 1. Admin patch via admin endpoint
    resp_admin_patch = client.patch(
        f"/api/admin/courses/{cid}",
        json={"status": "needs_attention"},
        headers=ADMIN_HEADERS,
    )
    assert resp_admin_patch.status_code == 200
    assert resp_admin_patch.json()["course"]["status"] == "needs_attention"

    # 2. Admin delete via admin endpoint
    resp_admin_del = client.delete(
        f"/api/admin/courses/{cid}",
        headers=ADMIN_HEADERS,
    )
    assert resp_admin_del.status_code == 200
    assert resp_admin_del.json()["status"] == "success"

    # Confirm deleted from Supabase
    assert get_course(cid) is None


def test_10_missing_course_returns_404():
    """Verify querying, updating, or deleting a missing course returns 404."""
    fake_id = f"cr-nonexistent-{uuid.uuid4().hex[:8]}"

    # Get single course
    resp_get = client.get(f"/api/institute/courses/{fake_id}")
    assert resp_get.status_code == 404

    # Patch
    resp_patch = client.patch(
        f"/api/institute/courses/{fake_id}",
        json={"enrolment_capacity": 50},
        headers=INSTITUTE_1_HEADERS,
    )
    assert resp_patch.status_code == 404

    # Delete
    resp_del = client.delete(
        f"/api/institute/courses/{fake_id}",
        headers=INSTITUTE_1_HEADERS,
    )
    assert resp_del.status_code == 404


def test_11_downstream_intelligence_reflects_supabase_courses():
    """Verify curriculum audit and recommendations consume courses from Supabase."""
    cid = f"cr-audit-{uuid.uuid4().hex[:8]}"
    course_data = {
        "id": cid,
        "name": "State-of-the-Art Quantum Algorithms",
        "institute": "COEP Pune",
        "district": "Pune",
        "category": "Quantum Computing",
        "enrolment_count": 30,
        "status": "active",
        "source": "USER_SUBMITTED",
        "is_demo": False,
    }
    get_client().table("courses").insert(course_data).execute()

    # Curriculum audit endpoint
    resp_audit = client.get("/api/curriculum/audit")
    assert resp_audit.status_code == 200
    audited = resp_audit.json().get("courses", [])
    assert any(c.get("course_id") == cid or c.get("id") == cid for c in audited)


def test_12_phase32a_phase32b_phase32c_remain_functional():
    """Verify previous migrations (feedback, demands, student data) remain intact and passing."""
    from app.repositories.supabase_repository import list_employer_feedback
    feedbacks = list_employer_feedback()
    assert isinstance(feedbacks, list)

    from app.repositories.supabase_repository import list_employer_demands
    demands = list_employer_demands()
    assert isinstance(demands, list)

    from app.repositories.supabase_repository import list_student_profiles, list_student_assessments
    profiles = list_student_profiles()
    assessments = list_student_assessments()
    assert isinstance(profiles, list)
    assert isinstance(assessments, list)


def test_13_student_cannot_probe_nonexistent_course():
    fake_id = f"cr-missing-{uuid.uuid4().hex[:8]}"
    resp_patch = client.patch(f"/api/institute/courses/{fake_id}", json={"name": "Hacked"}, headers=STUDENT_HEADERS)
    assert resp_patch.status_code == 403

    resp_del = client.delete(f"/api/institute/courses/{fake_id}", headers=STUDENT_HEADERS)
    assert resp_del.status_code == 403


def test_14_delete_course_by_course_id_column():
    cid = f"cr-col-{uuid.uuid4().hex[:8]}"
    row = {
        "id": f"row-{uuid.uuid4().hex[:8]}",
        "course_id": cid,
        "name": "Distinct ID Course",
        "district": "Pune",
        "category": "Tech",
        "status": "active",
        "is_demo": False,
    }
    get_client().table("courses").insert(row).execute()
    assert get_course(cid) is not None

    deleted = delete_course_repo(cid)
    assert deleted is True
    assert get_course(cid) is None


def test_15_list_courses_with_is_demo_filter():
    cid_real = f"cr-real-{uuid.uuid4().hex[:8]}"
    cid_demo = f"cr-demo-{uuid.uuid4().hex[:8]}"
    get_client().table("courses").insert({
        "id": cid_real,
        "name": "Real Course Filter Test",
        "is_demo": False,
    }).execute()
    get_client().table("courses").insert({
        "id": cid_demo,
        "name": "Demo Course Filter Test",
        "is_demo": True,
    }).execute()

    real_courses = list_courses(is_demo=False)
    real_ids = [c["id"] for c in real_courses]
    assert cid_real in real_ids
    assert cid_demo not in real_ids

    demo_courses = list_courses(is_demo=True)
    demo_ids = [c["id"] for c in demo_courses]
    assert cid_demo in demo_ids
    assert cid_real not in demo_ids


def test_16_delete_course_repo_empty_id_returns_false():
    assert delete_course_repo("") is False
