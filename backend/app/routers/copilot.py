"""AI Copilot API — conversational assistant grounded in SkillSetu data."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, StrictStr
from app.core.security import get_optional_current_user

router = APIRouter()


class CopilotContextData(BaseModel):
    target_role: StrictStr | None = None
    student_name: StrictStr | None = None
    student_id: StrictStr | None = None
    topic: StrictStr | None = None
    recommendation_title: StrictStr | None = None
    missing_prerequisites: list[StrictStr] | None = None
    relevant_courses: list[dict] | None = None
    source: StrictStr | None = None

    model_config = {"extra": "allow"}


class CopilotQuery(BaseModel):
    question: str
    role: str = "student"  # government, institute, student, employer
    district: str | None = None
    student_id: str | None = None
    context_data: CopilotContextData | None = None
    is_demo: bool | None = None


class CareerExplainQuery(BaseModel):
    student_id: str = Field(..., description="Target candidate ID from student profiles or assessments")
    question: str | None = Field(default=None, description="Specific query or custom prompt")
    district: str | None = None
    is_demo: bool | None = None


@router.post("/copilot/ask")
async def ask_copilot(
    query: CopilotQuery,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Conversational intelligence query grounded in Maharashtra labour datasets and candidate recommendations."""
    # ponytail: import here to avoid circular deps and keep startup fast
    from ai.copilot import handle_question
    from app.routers.student import _verify_student_recommendations_access

    ctx_data = query.context_data.model_dump() if query.context_data else None
    effective_student_id = query.student_id or (ctx_data.get("student_id") if ctx_data else None)

    # SECURITY: Reject unauthorized access before private recommendation data is loaded
    if effective_student_id:
        _verify_student_recommendations_access(effective_student_id, current_user)

    answer = await handle_question(
        question=query.question,
        role=query.role,
        district=query.district,
        student_id=effective_student_id,
        context_data=ctx_data,
        current_user=current_user,
        is_demo=query.is_demo,
    )
    return answer


@router.post("/copilot/explain-career")
async def explain_career(
    query: CareerExplainQuery,
    current_user: dict | None = Depends(get_optional_current_user),
):
    """Direct explainability endpoint for candidate career recommendations connecting assessments, validated employer demand, and schemes."""
    from ai.copilot import handle_question
    from app.routers.student import _verify_student_recommendations_access

    # SECURITY: Enforce ownership or privileged-role authorization before loading candidate data
    _verify_student_recommendations_access(query.student_id, current_user)

    q = query.question or "Explain my career recommendations, skill gaps, and next learning roadmap steps."
    answer = await handle_question(
        question=q,
        role="student",
        district=query.district,
        student_id=query.student_id,
        current_user=current_user,
        is_demo=query.is_demo,
    )
    return answer
