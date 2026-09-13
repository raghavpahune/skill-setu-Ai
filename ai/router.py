import os
import sys
import time
import logging
from pathlib import Path
from typing import Any

_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from ai.provider import LLMProvider
from ai.gemini_provider import GeminiProvider
from ai.demo_provider import DemoProvider

logger = logging.getLogger("skillsetu.ai.router")

TASK_CAREER_COPILOT = "career_copilot"
TASK_SKILL_GAP_ANALYSIS = "skill_gap_analysis"
TASK_LEARNING_ROADMAP = "learning_roadmap"
TASK_EMPLOYEE_TRANSITION = "employee_transition"
TASK_EMPLOYER_CANDIDATE_ANALYSIS = "employer_candidate_analysis"
TASK_INSTITUTE_CURRICULUM_ANALYSIS = "institute_curriculum_analysis"
TASK_GOVERNMENT_POLICY_ANALYSIS = "government_policy_analysis"
TASK_DATA_INSIGHT_GENERATION = "data_insight_generation"

SUPPORTED_AI_TASKS = [
    TASK_CAREER_COPILOT,
    TASK_SKILL_GAP_ANALYSIS,
    TASK_LEARNING_ROADMAP,
    TASK_EMPLOYEE_TRANSITION,
    TASK_EMPLOYER_CANDIDATE_ANALYSIS,
    TASK_INSTITUTE_CURRICULUM_ANALYSIS,
    TASK_GOVERNMENT_POLICY_ANALYSIS,
    TASK_DATA_INSIGHT_GENERATION,
]


class AIRouter:
    def __init__(self):
        self._fallback_provider = DemoProvider()
        self._last_error_category = "NONE"
        self._task_counts: dict[str, int] = {t: 0 for t in SUPPORTED_AI_TASKS}

    def _resolve_gemini(self) -> GeminiProvider | None:
        try:
            from app.core.providers_config import is_gemini_configured
            if is_gemini_configured():
                prov = GeminiProvider()
                if prov.api_key:
                    return prov
        except Exception as e:
            logger.warning(f"[AIRouter] Failed initializing GeminiProvider: {e}")
        return None

    def get_last_error_category(self) -> str:
        return self._last_error_category

    def get_supported_tasks(self) -> list[str]:
        return list(SUPPORTED_AI_TASKS)

    async def route_task(
        self,
        task_category: str,
        prompt: str,
        context: dict | None = None,
        is_demo: bool | None = None,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        if task_category not in self._task_counts:
            self._task_counts[task_category] = 0
        self._task_counts[task_category] += 1

        start_time = time.perf_counter()
        normalized_task = task_category if task_category in SUPPORTED_AI_TASKS else TASK_CAREER_COPILOT

        gemini_prov = None if is_demo is True else self._resolve_gemini()

        if gemini_prov is not None:
            try:
                answer = await gemini_prov.generate(prompt, context)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                self._last_error_category = "NONE"
                return {
                    "status": "success",
                    "answer": answer,
                    "provider": "gemini",
                    "model": getattr(gemini_prov, "model", "gemini-3.6-flash"),
                    "task_category": normalized_task,
                    "fallback_used": False,
                    "latency_ms": round(elapsed_ms, 2),
                    "error": None,
                }
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    self._last_error_category = "QUOTA_EXCEEDED"
                elif "timeout" in err_str or "timed out" in err_str:
                    self._last_error_category = "TIMEOUT"
                elif "401" in err_str or "403" in err_str or "api_key" in err_str:
                    self._last_error_category = "AUTH_FAILURE"
                else:
                    self._last_error_category = "NETWORK_ERROR"
                logger.warning(f"[AIRouter] Gemini failed for task '{normalized_task}' ({self._last_error_category}): {e}. Activating deterministic fallback.")

        if not gemini_prov and self._last_error_category == "NONE":
            self._last_error_category = "NOT_CONFIGURED"

        fallback_start = time.perf_counter()
        fallback_answer = await self._fallback_provider.generate(prompt, context)
        elapsed_ms = (time.perf_counter() - fallback_start) * 1000.0

        return {
            "status": "success",
            "answer": fallback_answer,
            "provider": "demo_fallback",
            "model": "rule-based-deterministic",
            "task_category": normalized_task,
            "fallback_used": True,
            "latency_ms": round(elapsed_ms, 2),
            "error": None if self._last_error_category == "NONE" else f"Failover triggered: {self._last_error_category}",
        }

    def get_diagnostics(self) -> dict[str, Any]:
        from app.core.providers_config import is_gemini_configured
        gemini_ok = is_gemini_configured()
        return {
            "primary_provider": "gemini",
            "primary_configured": gemini_ok,
            "fallback_provider": "demo_fallback",
            "fallback_available": True,
            "supported_tasks": list(SUPPORTED_AI_TASKS),
            "last_error_category": self._last_error_category,
            "task_invocations": dict(self._task_counts),
        }


ai_router = AIRouter()
