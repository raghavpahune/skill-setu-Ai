"""Comprehensive test suite for Copilot Gemini 3.6 Flash migration, fallback behavior, and API contract."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

backend_dir = Path(__file__).resolve().parent
root_dir = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))

from starlette.testclient import TestClient
from app.main import app
from app.db import load_demo_data
from ai.gemini_provider import GeminiProvider, MODELS
from ai.copilot import handle_question, _get_provider
from ai.demo_provider import DemoProvider

load_demo_data()
client = TestClient(app)


import pytest

pytestmark = pytest.mark.usefixtures("enable_demo_mode")


def test_gemini_provider_models_configuration():
    """Verify Gemini 3.6 Flash is the primary model and retired models are excluded."""
    assert "gemini-3.6-flash" in MODELS
    assert MODELS[0] == "gemini-3.6-flash"
    
    # Ensure retired legacy models are not in MODELS list
    retired = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
    for r in retired:
        assert r not in MODELS, f"Retired model '{r}' found in MODELS list: {MODELS}"

    prov = GeminiProvider()
    assert prov.model == "gemini-3.6-flash"


def test_copilot_offline_fallback_behavior():
    """Verify offline fallback produces grounded intelligence when no key is present."""
    old_key = os.environ.pop("GEMINI_API_KEY", None)
    old_gkey = os.environ.pop("GOOGLE_API_KEY", None)

    try:
        prov = _get_provider()
        assert isinstance(prov, DemoProvider)

        res = client.post("/api/copilot/ask", json={
            "question": "What are the biggest skill gaps in Pune?",
            "role": "student"
        })
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert data["role"] == "student"
        assert data["demo_mode"] is True
        assert data["data_grounded"] is True
        assert data["model"] == "Rule-Based Offline Intelligence"
        assert "Pune" in data["answer"] or "Skill" in data["answer"]
    finally:
        if old_key:
            os.environ["GEMINI_API_KEY"] = old_key
        if old_gkey:
            os.environ["GOOGLE_API_KEY"] = old_gkey


def test_copilot_live_generation_success():
    """Verify live Gemini 3.6 Flash inference returns truthful model metadata."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_test_key_12345"}):
        with patch.object(GeminiProvider, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "### Maharashtra Labour Analysis\nDemand for Python is up 25%."
            
            res = client.post("/api/copilot/ask", json={
                "question": "What is the demand trend for Python?",
                "role": "student",
                "is_demo": False
            })
            assert res.status_code == 200
            data = res.json()
            assert data["demo_mode"] is False
            assert data["model"] == "gemini-3.6-flash"
            assert "Maharashtra Labour Analysis" in data["answer"]
            assert data["data_grounded"] is True
            # Verify key is never exposed
            assert "dummy_test_key_12345" not in str(data)


def test_copilot_live_error_graceful_fallback():
    """Verify that if live Gemini encounters an error, it falls back to DemoProvider without crashing."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy_test_key_12345"}):
        with patch.object(GeminiProvider, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = RuntimeError("404 Model Not Found or Quota Exceeded")
            
            res = client.post("/api/copilot/ask", json={
                "question": "Tell me about skill gaps",
                "role": "student"
            })
            assert res.status_code == 200
            data = res.json()
            assert data["demo_mode"] is True
            assert data["model"] == "Rule-Based Offline Intelligence"
            assert "answer" in data
            assert len(data["answer"]) > 10


def test_copilot_roles_and_grounding():
    """Test copilot context grounding across government, institute, employer, and student roles."""
    roles = ["government", "institute", "employer", "student"]
    for r in roles:
        res = client.post("/api/copilot/ask", json={
            "question": "Analyze labour market demand and curriculum alignment",
            "role": r
        })
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == r
        assert data["data_grounded"] is True
        assert len(data["answer"]) > 20


def test_health_ai_endpoint():
    """Verify /api/health/ai returns diagnostic structure without leaking keys."""
    res = client.get("/api/health/ai")
    assert res.status_code == 200
    diag = res.json()
    assert "gemini_key_present" in diag
    assert "installed_sdks" in diag
    assert "httpx-rest" in diag["installed_sdks"]
    assert "api_key" not in diag


def test_copilot_district_context_explicit_parameter():
    """Verify that passing explicit district parameter grounds response to that district."""
    for dist in ["Amravati", "Pune", "Thane", "Nagpur"]:
        res = client.post("/api/copilot/ask", json={
            "question": f"Give me a detailed workforce intelligence briefing for {dist}.",
            "role": "government",
            "district": dist
        })
        assert res.status_code == 200
        data = res.json()
        assert data["data_grounded"] is True
        assert dist in data["answer"]
        assert "Labour & Industrial Demand" in data["answer"] or "Intelligence" in data["answer"]


def test_copilot_district_context_empty_or_unknown():
    """Verify graceful handling when district context is empty or unindexed."""
    res = client.post("/api/copilot/ask", json={
        "question": "What are the priority training areas?",
        "role": "government",
        "district": None
    })
    assert res.status_code == 200
    data = res.json()
    assert data["data_grounded"] is True
    assert len(data["answer"]) > 10


if __name__ == "__main__":
    test_gemini_provider_models_configuration()
    test_copilot_offline_fallback_behavior()
    test_copilot_live_generation_success()
    test_copilot_live_error_graceful_fallback()
    test_copilot_roles_and_grounding()
    test_health_ai_endpoint()
    test_copilot_district_context_explicit_parameter()
    test_copilot_district_context_empty_or_unknown()
    print("\nALL COPILOT & GEMINI 3.6 FLASH TESTS PASSED SUCCESSFULLY!")
