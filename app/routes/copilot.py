from fastapi import APIRouter, HTTPException

from app.models.schemas import CopilotRequest, CopilotResponse
from app.services.copilot_service import run_copilot_session

router = APIRouter()


@router.post(
    "/generate",
    response_model=CopilotResponse,
    summary="Run Session Co-Pilot",
    description="Submit a session brief and optional context. Returns structured creative direction.",
)
async def run_session(request: CopilotRequest) -> CopilotResponse:
    try:
        return await run_copilot_session(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session generation failed: {str(e)}")
