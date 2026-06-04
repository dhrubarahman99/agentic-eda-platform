from fastapi import APIRouter
from app.models.schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse, summary="Health check", tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")
