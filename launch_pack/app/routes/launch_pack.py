from fastapi import APIRouter, HTTPException, status
from app.models.request import LaunchPackRequest
from app.models.response import LaunchPackResponse
from app.services.launch_pack_service import LaunchPackService
from app.providers.base import ProviderError

router = APIRouter()
service = LaunchPackService()


@router.post(
    "/generate-launch-pack",
    response_model=LaunchPackResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a complete beat launch pack",
    description=(
        "Accepts beat metadata and returns a fully structured launch pack: "
        "title ideas, YouTube SEO pack, short-form content, outreach copy, "
        "type beat positioning, and a 7-day launch plan."
    ),
)
async def generate_launch_pack(req: LaunchPackRequest) -> LaunchPackResponse:
    try:
        return await service.generate(req)
    except ProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error generating launch pack.",
        )
