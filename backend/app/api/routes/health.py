"""Health Check API"""
from fastapi import APIRouter

from app.config.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
