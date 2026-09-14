import asyncio
import sys
import time
import logging
from pathlib import Path
from typing import Any

_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from ai.gemini_provider import GeminiProvider
from ai.demo_provider import DemoProvider
from app.core.data_mode import is_explicit_demo_mode

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


def resolve_workload_gemini_provider(task_category: str) -> GeminiProvider | None:
    try:
        from app.core.providers_config import (
            get_workload_ai_key,
            is_workload_ai_configured,
            get_workload_provider,
        )
        if get_workload_provider(task_category) != "gemini":
            return None
        if is_workload_ai_configured(task_category):
            key = get_workload_ai_key(task_category)
            prov = GeminiProvider(api_key=key)
            if prov.api_key:
                return prov
    except Exception as e:
        logger.warning(f"[AIRouter] Failed initializing GeminiProvider for '{task_category}': {e}")
    return None


class AIRouter:

    def __init__(self):
        self._deterministic_fallback = DemoProvider()
        self._last_error_category: str = "NONE"
        self._task_counts: dict[str, int] = {task: 0 for task in SUPPORTED_AI_TASKS}

    def _resolve_gemini_for_task(self, task_category: str) -> GeminiProvider | None:
        return resolve_workload_gemini_provider(task_category)

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
        if task_category not in SUPPORTED_AI_TASKS:
            raise ValueError(f"Unsupported AI task category: {task_category}. Supported categories: {SUPPORTED_AI_TASKS}")

        if task_category not in self._task_counts:
            self._task_counts[task_category] = 0
        self._task_counts[task_category] += 1

        start_time = time.perf_counter()

        if is_explicit_demo_mode(is_demo):
            fallback_start = time.perf_counter()
            fallback_answer = await self._deterministic_fallback.generate(prompt, context)
            elapsed_ms = (time.perf_counter() - fallback_start) * 1000.0
            return {
                "status": "success",
                "answer": fallback_answer,
                "provider": "deterministic_fallback",
                "model": "rule-based-deterministic",
                "task_category": task_category,
                "fallback_used": True,
                "advisory": True,
                "latency_ms": round(elapsed_ms, 2),
                "error": None,
            }

        from app.core.providers_config import get_workload_provider
        configured_provider = get_workload_provider(task_category)

        request_error_category = "NONE"
        gemini_prov = None

        if configured_provider == "gemini":
            gemini_prov = self._resolve_gemini_for_task(task_category)
            if gemini_prov is not None:
                try:
                    answer = await asyncio.wait_for(
                        gemini_prov.generate(prompt, context),
                        timeout=timeout_seconds,
                    )
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    self._last_error_category = "NONE"
                    return {
                        "status": "success",
                        "answer": answer,
                        "provider": "gemini",
                        "model": getattr(gemini_prov, "model", "gemini-3.6-flash"),
                        "task_category": task_category,
                        "fallback_used": False,
                        "advisory": True,
                        "latency_ms": round(elapsed_ms, 2),
                        "error": None,
                    }
                except Exception as e:
                    err_str = str(e).lower()
                    if isinstance(e, asyncio.TimeoutError) or "timeout" in err_str or "timed out" in err_str:
                        request_error_category = "TIMEOUT"
                    elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                        request_error_category = "QUOTA_EXCEEDED"
                    elif "401" in err_str or "403" in err_str or "api_key" in err_str:
                        request_error_category = "AUTH_FAILURE"
                    else:
                        request_error_category = "NETWORK_ERROR"
                    self._last_error_category = request_error_category
                    logger.warning(f"[AIRouter] Gemini failed for task '{task_category}' ({request_error_category}): {e}. Activating deterministic fallback.")
            else:
                request_error_category = "NOT_CONFIGURED"
                self._last_error_category = "NOT_CONFIGURED"
        elif configured_provider in ("deterministic_fallback", "demo_fallback", "demo"):
            request_error_category = "NONE"
        else:
            request_error_category = "UNSUPPORTED_PROVIDER"
            self._last_error_category = "UNSUPPORTED_PROVIDER"

        fallback_start = time.perf_counter()
        fallback_answer = await self._deterministic_fallback.generate(prompt, context)
        elapsed_ms = (time.perf_counter() - fallback_start) * 1000.0

        return {
            "status": "success",
            "answer": fallback_answer,
            "provider": "deterministic_fallback",
            "model": "rule-based-deterministic",
            "task_category": task_category,
            "fallback_used": True,
            "advisory": True,
            "latency_ms": round(elapsed_ms, 2),
            "error": None if request_error_category == "NONE" else f"Failover triggered: {request_error_category}",
        }

    def get_diagnostics(self) -> dict[str, Any]:
        from app.core.providers_config import (
            get_workload_provider,
            is_gemini_configured,
            is_workload_ai_configured,
        )
        gemini_ok = is_gemini_configured() or any(
            get_workload_provider(task) == "gemini"
            and is_workload_ai_configured(task)
            for task in SUPPORTED_AI_TASKS
        )
        return {
            "real_provider": "gemini",
            "real_provider_configured": gemini_ok,
            "fallback_mechanism": "deterministic_fallback",
            "fallback_available": True,
            "supported_tasks": list(SUPPORTED_AI_TASKS),
            "last_error_category": self._last_error_category,
            "task_invocations": dict(self._task_counts),
        }


ai_router = AIRouter()
