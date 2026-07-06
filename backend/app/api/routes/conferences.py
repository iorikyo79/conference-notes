"""Conferences API Routes"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.schemas import ConferenceCreate, SessionCreate
from app.services.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_conferences():
    """학회 목록 조회"""
    conferences = storage.get_conferences()
    return {"conferences": conferences, "count": len(conferences)}


@router.get("/{conference_id}")
async def get_conference(conference_id: str):
    """특정 학회 상세 조회 (일자, 세션 포함)"""
    conf = storage.get_conference(conference_id)
    if not conf:
        raise HTTPException(status_code=404, detail=f"Conference '{conference_id}' not found")
    return conf


@router.post("/")
async def create_conference(request: ConferenceCreate):
    """학회 생성"""
    existing = storage.get_conference(request.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Conference '{request.id}' already exists")

    conf_data = request.model_dump()
    conf_data["created_at"] = datetime.now().isoformat()

    saved = storage.save_conference(conf_data)
    logger.info(f"Created conference: {request.id}")
    return saved


@router.post("/{conference_id}/days/{day_date}/sessions")
async def add_session(conference_id: str, day_date: str, request: SessionCreate):
    """학회의 특정 일자에 세션 추가"""
    conf = storage.get_conference(conference_id)
    if not conf:
        raise HTTPException(status_code=404, detail=f"Conference '{conference_id}' not found")

    # 해당 일자가 있는지 확인
    day_exists = False
    for day in conf.get("days", []):
        if day["date"] == day_date:
            day_exists = True
            break

    if not day_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Day '{day_date}' not found in conference '{conference_id}'"
        )

    session_data = request.model_dump()
    session_data["id"] = storage.generate_id()
    session_data["day_date"] = day_date

    updated_conf = storage.add_session_to_conference(
        conference_id, day_date, session_data
    )
    logger.info(f"Added session '{session_data['id']}' to {conference_id}/{day_date}")
    return session_data


@router.delete("/{conference_id}/sessions/{session_id}")
async def delete_session(conference_id: str, session_id: str):
    """학회에서 특정 세션 삭제 (연관 노트도 함께 삭제)"""
    conf = storage.get_conference(conference_id)
    if not conf:
        raise HTTPException(status_code=404, detail=f"Conference '{conference_id}' not found")

    # 세션이 존재하는지 확인
    session_exists = False
    session_title = ""
    for day in conf.get("days", []):
        for sess in day.get("sessions", []):
            if sess["id"] == session_id:
                session_exists = True
                session_title = sess.get("title", "")
                break
        if session_exists:
            break

    if not session_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found in conference '{conference_id}'"
        )

    storage.delete_session_from_conference(conference_id, session_id)
    logger.info(f"Deleted session '{session_id}' ({session_title}) from {conference_id}")
    return {
        "message": f"Session '{session_id}' deleted",
        "session_title": session_title,
        "deleted": True,
    }
