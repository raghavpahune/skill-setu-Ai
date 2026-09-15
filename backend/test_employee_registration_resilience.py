import pytest
from unittest.mock import MagicMock, patch
from app.db import save_user, get_user_by_email, get_user_by_id, _cache


def test_save_user_employee_fallback_on_constraint_violation():
    mock_client = MagicMock()
    call_counts = {"count": 0}

    def mock_execute():
        call_counts["count"] += 1
        if call_counts["count"] == 1:
            raise RuntimeError('check constraint "users_role_check" is violated by value "EMPLOYEE"')
        return MagicMock(data=[{"id": "usr-employee-test99"}])

    mock_table = MagicMock()
    mock_table.upsert.return_value.execute = mock_execute
    mock_client.table.return_value = mock_table

    with patch("app.db.get_supabase_client", return_value=mock_client):
        user_data = {
            "id": "usr-employee-test99",
            "email": "employee_test99@skillsetu.gov.in",
            "role": "EMPLOYEE",
            "name": "Test Employee",
        }
        res = save_user(user_data)
        assert res["role"] == "EMPLOYEE"
        assert call_counts["count"] == 2
        first_call_args = mock_table.upsert.call_args_list[0][0][0]
        second_call_args = mock_table.upsert.call_args_list[1][0][0]
        assert first_call_args["role"] == "EMPLOYEE"
        assert second_call_args["role"] == "STUDENT"


def test_get_user_by_email_restores_employee_role():
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.data = [{
        "id": "usr-employee-abc12345",
        "email": "vikram@example.com",
        "role": "STUDENT",
        "name": "Vikram Shinde",
    }]
    mock_client.table.return_value.select.return_value.ilike.return_value.execute.return_value = mock_res

    _cache["users"] = []
    with patch("app.db.get_supabase_client", return_value=mock_client):
        user = get_user_by_email("vikram@example.com")
        assert user is not None
        assert user["role"] == "EMPLOYEE"


def test_get_user_by_id_restores_employee_role():
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.data = [{
        "id": "usr-employee-abc12345",
        "email": "vikram@example.com",
        "role": "STUDENT",
        "name": "Vikram Shinde",
    }]
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_res

    _cache["users"] = []
    with patch("app.db.get_supabase_client", return_value=mock_client):
        user = get_user_by_id("usr-employee-abc12345")
        assert user is not None
        assert user["role"] == "EMPLOYEE"
