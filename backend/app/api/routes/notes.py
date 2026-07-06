"""Notes API Routes"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.models.schemas import NoteCreate, NoteUpdate
from app.services.storage import storage
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)
router = APIRouter()


class OrganizeRequest(BaseModel):
    """스크립트 정리 요청"""
    raw_text: str = Field(..., description="정리할 원본 텍스트 (발표 스크립트, 필사본 등)")


class OrganizeResponse(BaseModel):
    """스크립트 정리 응답"""
    organized_content: str = Field(..., description="정리된 마크다운")
    keywords: list = Field(default_factory=list, description="추출된 키워드")
    model_used: bool = Field(..., description="LLM 사용 여부")


class OrganizeAndSaveRequest(BaseModel):
    """
    외부 AI 에이전트용: 스크립트 정리 + 노트 저장을 한 번에 처리

    사용 방법:
    1. session_id와 raw_text를 POST
    2. 시스템이 세션 정보(제목, 연자)를 자동으로 조회
    3. LLM으로 스크립트 정리 (ZHIPU_API_KEY 필요)
    4. 정리된 마크다운을 노트로 저장
    5. 생성된 노트 ID와 내용 반환
    """
    session_id: str = Field(..., description="세션 ID")
    conference_id: str = Field(..., description="학회 ID")
    raw_text: str = Field(..., description="정리할 원본 텍스트")
    mode: str = Field(
        "replace",
        description="replace: 기존 노트 덮어쓰기, append: 기존 노트 뒤에 추가, new: 새 노트 생성"
    )


@router.get("/")
async def get_notes(session_id: str = Query(None, description="세션 ID로 필터링")):
    """노트 목록 조회 (세션 필터링 가능)"""
    notes = storage.get_notes(session_id=session_id)
    return {"notes": notes, "count": len(notes)}


@router.get("/{note_id}")
async def get_note(note_id: str):
    """특정 노트 조회"""
    note = storage.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return note


@router.post("/")
async def create_note(request: NoteCreate):
    """노트 생성"""
    note_data = {
        "id": storage.generate_id(),
        "session_id": request.session_id,
        "conference_id": request.conference_id,
        "content": request.content,
        "tags": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "is_starred": False,
    }
    saved = storage.save_note(note_data)
    logger.info(f"Created note: {saved['id']} for session {request.session_id}")
    return saved


@router.put("/{note_id}")
async def update_note(note_id: str, request: NoteUpdate):
    """노트 수정 (자동저장에서 사용)"""
    existing = storage.get_note(note_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")

    # None이 아닌 필드만 업데이트
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        return existing

    updated = storage.update_note(note_id, updates)
    return updated


@router.delete("/empty/bulk")
async def delete_empty_notes(
    conference_id: str = Query(None, description="학회 ID로 필터링"),
    session_id: str = Query(None, description="세션 ID로 필터링"),
):
    """
    빈 노트(content가 비어있는 노트) 일괄 삭제.

    옵션 필터:
    - conference_id: 특정 학회의 빈 노트만 삭제
    - session_id: 특정 세션의 빈 노트만 삭제
    """
    notes = storage.get_notes()
    empty_notes = [
        n for n in notes
        if (not n.get("content") or not n.get("content", "").strip())
        and (not conference_id or n.get("conference_id") == conference_id)
        and (not session_id or n.get("session_id") == session_id)
    ]

    deleted_ids = []
    for n in empty_notes:
        storage.delete_note(n["id"])
        deleted_ids.append(n["id"])

    logger.info(f"Deleted {len(deleted_ids)} empty notes"
                f"{' (conference=' + conference_id + ')' if conference_id else ''}"
                f"{' (session=' + session_id + ')' if session_id else ''}")

    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
    }


@router.delete("/{note_id}")
async def delete_note(note_id: str):
    """노트 삭제"""
    deleted = storage.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    logger.info(f"Deleted note: {note_id}")
    return {"message": f"Note '{note_id}' deleted", "deleted": True}


@router.post("/{note_id}/organize")
async def organize_note_script(note_id: str, request: OrganizeRequest):
    """
    노트의 원본 텍스트(발표 스크립트)를 LLM으로 정리하여
    구조화된 마크다운으로 변환. 노트 내용은 덮어쓰지 않고 결과만 반환.
    """
    note = storage.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")

    # 세션 정보에서 title, speaker 확보
    session_title = ""
    speaker = None
    conference_id = note.get("conference_id")
    session_id = note.get("session_id")
    conf = storage.get_conference(conference_id) if conference_id else None
    if conf:
        for day in conf.get("days", []):
            for sess in day.get("sessions", []):
                if sess["id"] == session_id:
                    session_title = sess.get("title", "")
                    speaker = sess.get("speaker")
                    break

    result = llm_service.organize_script(
        raw_text=request.raw_text,
        session_title=session_title,
        speaker=speaker,
    )

    logger.info(
        f"Organized script for note {note_id}: "
        f"{len(result['organized_content'])} chars, LLM={result['model_used']}"
    )

    return result


@router.post("/organize-and-save")
async def organize_and_save(request: OrganizeAndSaveRequest):
    """
    외부 AI 에이전트용: 스크립트 정리 + 노트 저장을 한 번에 처리

    1. 세션 정보(제목, 연자) 자동 조회
    2. LLM으로 스크립트 정리
    3. 정리된 마크다운을 노트로 저장
    4. 결과 반환

    mode 옵션:
    - replace: 기존 노트 덮어쓰기 (기본값)
    - append: 기존 노트 뒤에 추가
    - new: 새 노트 생성
    """
    # 1. 세션 정보 조회
    session_title = ""
    speaker = None
    conf = storage.get_conference(request.conference_id) if request.conference_id else None
    if conf:
        for day in conf.get("days", []):
            for sess in day.get("sessions", []):
                if sess["id"] == request.session_id:
                    session_title = sess.get("title", "")
                    speaker = sess.get("speaker")
                    break

    # 2. 스크립트 정리
    result = llm_service.organize_script(
        raw_text=request.raw_text,
        session_title=session_title,
        speaker=speaker,
    )
    organized = result["organized_content"]

    if not organized.strip():
        raise HTTPException(status_code=422, detail="정리 결과가 비어있습니다")

    # 3. 모드에 따라 노트 저장
    if request.mode == "new":
        # 새 노트 생성
        note_data = {
            "id": storage.generate_id(),
            "session_id": request.session_id,
            "conference_id": request.conference_id,
            "content": organized,
            "tags": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_starred": False,
        }
        saved = storage.save_note(note_data)
        note_id = saved["id"]
    else:
        # 기존 노트 조회
        existing_notes = storage.get_notes(session_id=request.session_id)
        if existing_notes:
            target = existing_notes[0]
            note_id = target["id"]

            if request.mode == "append":
                separator = "\n\n---\n\n" if target.get("content") else ""
                new_content = (target.get("content") or "") + separator + organized
            else:  # replace
                new_content = organized

            storage.update_note(note_id, {
                "content": new_content,
                "updated_at": datetime.now().isoformat(),
            })
        else:
            # 기존 노트가 없으면 새로 생성
            note_data = {
                "id": storage.generate_id(),
                "session_id": request.session_id,
                "conference_id": request.conference_id,
                "content": organized,
                "tags": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "is_starred": False,
            }
            saved = storage.save_note(note_data)
            note_id = saved["id"]

    logger.info(
        f"Organize-and-save: session={request.session_id}, "
        f"note={note_id}, mode={request.mode}, "
        f"content={len(organized)} chars, LLM={result['model_used']}"
    )

    return {
        "note_id": note_id,
        "session_id": request.session_id,
        "session_title": session_title,
        "speaker": speaker,
        "mode": request.mode,
        "organized_content": organized,
        "keywords": result["keywords"],
        "model_used": result["model_used"],
        "content_length": len(organized),
    }
