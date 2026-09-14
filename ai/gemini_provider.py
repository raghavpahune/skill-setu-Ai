"""Gemini LLM provider implementation with safe diagnostics, REST support, and google-genai SDK."""
import os
import json
import logging
import httpx
from ai.provider import LLMProvider

logger = logging.getLogger("skillsetu.ai.gemini")

# Primary supported model: gemini-3.6-flash (legacy models gemini-1.5-*, 2.0-*, 2.5-*, gemini-pro are retired by Google)
MODELS = ["gemini-3.6-flash"]


class GeminiProvider(LLMProvider):
    """Robust Google Gemini provider supporting google-genai SDK (async/sync) and Direct REST HTTP failover."""

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or self._resolve_api_key()).strip().strip("'\"")
        self.client = None
        self.model = "gemini-3.6-flash"
        self._sdk = None

        if not self.api_key:
            return

        # Initialize official google-genai SDK client if installed, otherwise fallback to direct REST
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self._sdk = "google-genai"
            logger.info("[GeminiProvider] Initialized google-genai SDK.")
        except Exception:
            self.client = "httpx-rest"
            self._sdk = "httpx-rest"
            logger.info("[GeminiProvider] Initialized direct REST client.")

    def _resolve_api_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        if not key:
            try:
                from app.config import settings
                key = settings.gemini_api_key or ""
            except Exception:
                pass
        return key.strip().strip("'\"")

    async def diagnose(self) -> dict:
        """Run a safe diagnostic probe to test the Gemini connection without exposing secrets."""
        key_present = bool(self.api_key)
        key_len = len(self.api_key) if key_present else 0

        installed_sdks = []
        try:
            import google.genai
            installed_sdks.append("google-genai")
        except Exception:
            pass

        installed_sdks.append("httpx-rest")

        if not key_present:
            return {
                "gemini_key_present": False,
                "key_length": 0,
                "provider": "demo",
                "model": "rule-based-demo",
                "status": "error",
                "error_code": "MISSING_API_KEY",
                "error_message": "No GEMINI_API_KEY found in process environment.",
                "installed_sdks": installed_sdks,
            }

        # Perform live probe iterating through models until success
        last_failure = None
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            for model_name in MODELS:
                clean_model = model_name.replace("models/", "")
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": "Reply with 'OK'"}]}]
                    }
                    res = await http_client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    if res.status_code == 200:
                        res_json = res.json()
                        reply = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        self.model = clean_model
                        return {
                            "gemini_key_present": True,
                            "key_length": key_len,
                            "provider": "gemini",
                            "model": clean_model,
                            "status": "ok",
                            "http_status": 200,
                            "probe_reply": reply,
                            "installed_sdks": installed_sdks,
                        }
                    else:
                        err_json = res.json().get("error", {}) if "application/json" in res.headers.get("content-type", "") else {}
                        last_failure = {
                            "gemini_key_present": True,
                            "key_length": key_len,
                            "provider": "gemini",
                            "model": clean_model,
                            "status": "error",
                            "http_status": res.status_code,
                            "error_code": err_json.get("status", f"HTTP_{res.status_code}"),
                            "error_message": err_json.get("message", res.text[:200]),
                            "installed_sdks": installed_sdks,
                        }
                        logger.warning(f"[Gemini Diagnose] Probe for {clean_model} failed ({res.status_code})")
                except Exception as probe_err:
                    last_failure = {
                        "gemini_key_present": True,
                        "key_length": key_len,
                        "provider": "gemini",
                        "model": clean_model,
                        "status": "error",
                        "error_code": "NETWORK_EXCEPTION",
                        "error_message": str(probe_err),
                        "installed_sdks": installed_sdks,
                    }

        return last_failure or {
            "gemini_key_present": True,
            "key_length": key_len,
            "provider": "gemini",
            "model": self.model,
            "status": "error",
            "error_code": "ALL_MODELS_FAILED",
            "installed_sdks": installed_sdks,
        }

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured in backend environment")

        system_instruction = (
            "You are SkillSetu AI Copilot, the official labour-market intelligence and curriculum-alignment assistant for Maharashtra, India. "
            "You provide evidence-based insights for Government, Institutes, Students, and Employers.\n\n"
            "CRITICAL GROUNDING RULES:\n"
            "1. For skill-specific questions, base your state-level numbers and claims ONLY on the verified data for that specific skill provided in the context.\n"
            "2. If 'data_available_for_skill' is false or a skill is not found in the dataset (e.g. Go/Golang, Rust, Ruby), you MUST explicitly state that the current SkillSetu Maharashtra dataset does NOT contain sufficient job records or accredited course data for that technology.\n"
            "3. When answering why a student should learn a competency or career recommendation:\n"
            "   a. Explain why the competency matters and connects directly to the student's target role.\n"
            "   b. Present current relevant Maharashtra labour-market demand signals (active vacancies, demand %, top hiring districts).\n"
            "   c. Clarify student alignment and missing prerequisite status.\n"
            "   d. Recommend ONLY real SkillSetu accredited courses present in the context; if none exist, state clearly that no matching course was found in the Maharashtra curriculum index.\n"
            "   e. Provide a practical step-by-step learning sequence (Prerequisites -> Core Concepts -> Tools -> Practical Project -> Advanced Competency -> NSQF Alignment -> Target Job Role).\n"
            "   f. End with an actionable next step for the student.\n"
            "4. NEVER cite overall Maharashtra aggregate statistics (e.g. 562 total jobs, Pune 150 jobs, or Python 26% demand) as evidence or demand numbers for an unindexed or different skill.\n"
            "5. Clearly distinguish between verified dataset facts (from the provided context), unavailable dataset information, and general technology context.\n"
            "6. Be concise, professional, clear, and actionable."
        )

        data_section = ""
        if context:
            data_section = f"\n\n--- MAHARASHTRA LABOUR-MARKET DATA CONTEXT ---\n{json.dumps(context, indent=2, default=str)}\n--- END DATA CONTEXT ---\n"

        full_prompt = f"{system_instruction}{data_section}\n\nUser Question: {prompt}"

        last_error = None

        # Strategy 1: official google-genai SDK (recommended by Google)
        if self._sdk == "google-genai" and self.client:
            for model_name in MODELS:
                clean_model = model_name.replace("models/", "")
                try:
                    if hasattr(self.client, "aio") and hasattr(self.client.aio, "models"):
                        response = await self.client.aio.models.generate_content(
                            model=clean_model,
                            contents=full_prompt,
                        )
                    else:
                        response = self.client.models.generate_content(
                            model=clean_model,
                            contents=full_prompt,
                        )
                    if response and response.text:
                        self.model = clean_model
                        logger.info(f"[GeminiProvider] Generated response via google-genai SDK (model: {clean_model})")
                        return response.text
                except Exception as e:
                    logger.warning(f"[GeminiProvider] google-genai SDK {clean_model} error: {e}")
                    last_error = str(e)

        # Strategy 2: Direct Async REST Call via httpx
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            for model_name in MODELS:
                clean_model = model_name.replace("models/", "")
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": full_prompt}
                                ]
                            }
                        ]
                    }
                    response = await http_client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    if response.status_code == 200:
                        res_json = response.json()
                        text = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            self.model = clean_model
                            logger.info(f"[GeminiProvider] Generated response via REST (model: {clean_model})")
                            return text
                    else:
                        err_data = response.json().get("error", {}) if "application/json" in response.headers.get("content-type", "") else {}
                        err_msg = err_data.get("message", response.text[:200])
                        logger.warning(f"[GeminiProvider] REST API model {clean_model} HTTP {response.status_code}: {err_msg}")
                        last_error = f"HTTP {response.status_code} ({clean_model}): {err_msg}"
                except Exception as e:
                    logger.warning(f"[GeminiProvider] REST attempt with {clean_model} failed: {e}")
                    last_error = str(e)

        raise RuntimeError(f"Gemini generation failed. Last error: {last_error}")
