"""Attachments API Routes"""
import logging
import os
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, BackgroundTasks, Body
from pathlib import Path

from app.config.settings import settings
from app.services.storage import storage
from app.services.pdf_extractor import PDFExtractor
from app.services.ocr_service import OCRService
from app.services.exif_service import exif_service
from app.services.session_matcher import session_matcher

logger = logging.getLogger(__name__)
router = APIRouter()

# 서비스 인스턴스
pdf_extractor = PDFExtractor()
ocr_service = OCRService()

# 허용 파일 확장자
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}


def _get_file_type(filename: str) -> str:
    """파일 확장자로부터 타입 반환"""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    elif ext in IMAGE_EXTENSIONS:
        return "image"
    else:
        return ext.lstrip(".") or "unknown"


def _extract_text_task(attachment_id: str, file_path: str, file_type: str):
    """백그라운드 텍스트 추출 태스크"""
    logger.info(f"Starting text extraction for attachment {attachment_id}")

    storage.update_attachment(attachment_id, {"extraction_status": "processing"})

    extracted_text = None

    if file_type == "pdf" and pdf_extractor.is_available():
        extracted_text = pdf_extractor.extract_text(file_path)
    elif file_type == "image" and ocr_service.is_available():
        extracted_text = ocr_service.extract_text(file_path)
    elif file_type == "pdf":
        extracted_text = "(PyMuPDF가 설치되지 않아 PDF 텍스트 추출을 사용할 수 없습니다.)"
    elif file_type == "image":
        extracted_text = "(Tesseract OCR이 설치되지 않아 이미지 텍스트 추출을 사용할 수 없습니다.)"

    if extracted_text is not None:
        storage.update_attachment(attachment_id, {
            "extracted_text": extracted_text,
            "extraction_status": "completed",
        })
        logger.info(f"Text extraction completed for {attachment_id}: {len(extracted_text)} chars")
    else:
        storage.update_attachment(attachment_id, {
            "extracted_text": "",
            "extraction_status": "failed",
        })
        logger.error(f"Text extraction failed for {attachment_id}")


@router.get("/")
async def get_attachments(session_id: str = Query(None, description="세션 ID로 필터링")):
    """첨부파일 목록 조회"""
    attachments = storage.get_attachments(session_id=session_id)
    return {"attachments": attachments, "count": len(attachments)}


@router.post("/upload")
async def upload_attachment(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Form(None),
    conference_id: str = Form(None),
):
    """파일 업로드 및 백그라운드 텍스트 추출 (EXIF 추출 포함)"""
    # 파일 확장자 검증
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 파일 크기 검증
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 파일 저장
    attachment_id = storage.generate_id()
    file_type = _get_file_type(file.filename or "unknown")
    safe_filename = f"{attachment_id}_{file.filename}"
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Saved uploaded file: {file_path}")

    # EXIF 추출 (표시용)
    exif_dt = None
    if file_type == "image":
        exif_dt = exif_service.extract_datetime(str(file_path))

    # 세션 자동 매칭 (session_id가 명시되지 않은 경우만)
    auto_session_id = session_id
    match_confidence = "manual" if session_id else "none"

    if not session_id and exif_dt and conference_id:
        conference = storage.get_conference(conference_id)
        match_result = session_matcher.match(exif_dt, conference)
        auto_session_id = match_result.session_id
        match_confidence = match_result.confidence

    # 첨부파일 메타데이터 저장
    attachment_data = {
        "id": attachment_id,
        "session_id": auto_session_id,
        "conference_id": conference_id,
        "filename": file.filename,
        "file_path": str(file_path),
        "file_type": file_type,
        "file_size": len(content),
        "extracted_text": None,
        "extraction_status": "pending",
        "exif_datetime": exif_dt.isoformat() if exif_dt else None,
        "match_confidence": match_confidence,
        "uploaded_at": datetime.now().isoformat(),
    }
    storage.save_attachment(attachment_data)

    # 백그라운드에서 텍스트 추출
    background_tasks.add_task(
        _extract_text_task,
        attachment_id,
        str(file_path),
        file_type,
    )

    return attachment_data


@router.post("/upload-batch")
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    conference_id: str = Form(...),
):
    """
    다중 이미지 배치 업로드 + EXIF 기반 세션 자동 분류.

    각 이미지에 대해:
    1. 디스크 저장
    2. EXIF DateTimeOriginal 추출
    3. 학회 세션 시간표와 매칭
    4. 자동 할당된 session_id와 함께 메타데이터 저장

    분류 결과 요약을 반환.
    """
    conference = storage.get_conference(conference_id)
    if not conference:
        raise HTTPException(status_code=404, detail=f"Conference '{conference_id}' not found")

    results = []
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "reason": f"지원하지 않는 파일 형식: {ext}",
            })
            continue

        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "reason": "파일 크기 초과",
            })
            continue

        # 파일 저장
        attachment_id = storage.generate_id()
        file_type = _get_file_type(file.filename or "unknown")
        safe_filename = f"{attachment_id}_{file.filename}"
        file_path = upload_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(content)

        # EXIF 추출 및 세션 매칭
        exif_dt = None
        match_result = None
        if file_type == "image":
            exif_dt = exif_service.extract_datetime(str(file_path))
            match_result = session_matcher.match(exif_dt, conference)

        auto_session_id = match_result.session_id if match_result else None
        confidence = match_result.confidence if match_result else "none"

        # 첨부파일 메타데이터 저장
        attachment_data = {
            "id": attachment_id,
            "session_id": auto_session_id,
            "conference_id": conference_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "file_type": file_type,
            "file_size": len(content),
            "extracted_text": None,
            "extraction_status": "pending",
            "exif_datetime": exif_dt.isoformat() if exif_dt else None,
            "match_confidence": confidence,
            "uploaded_at": datetime.now().isoformat(),
        }
        storage.save_attachment(attachment_data)

        # 백그라운드 텍스트 추출
        background_tasks.add_task(
            _extract_text_task,
            attachment_id,
            str(file_path),
            file_type,
        )

        results.append({
            "filename": file.filename,
            "attachment_id": attachment_id,
            "status": "uploaded",
            "session_id": auto_session_id,
            "session_title": match_result.matched_session.get("title") if match_result and match_result.matched_session else None,
            "exif_datetime": exif_dt.isoformat() if exif_dt else None,
            "confidence": confidence,
            "reason": match_result.reason if match_result else "이미지가 아님",
        })

    summary = {
        "total": len(results),
        "uploaded": sum(1 for r in results if r["status"] == "uploaded"),
        "rejected": sum(1 for r in results if r["status"] == "rejected"),
        "matched": sum(1 for r in results if r.get("session_id")),
        "unmatched": sum(1 for r in results if r["status"] == "uploaded" and not r.get("session_id")),
    }

    logger.info(f"Batch upload: {summary['uploaded']}/{summary['total']} uploaded, {summary['matched']} matched")

    return {"results": results, "summary": summary}


# === 캡션 생성 ===

def _generate_caption_task(attachment_id: str, file_path: str, session_title: str, speaker: str):
    """백그라운드 캡션 생성 태스크"""
    from app.services.llm_service import llm_service

    logger.info(f"Starting caption generation for {attachment_id}")
    storage.update_attachment(attachment_id, {"caption_status": "pending"})

    try:
        result = llm_service.generate_caption(file_path, session_title, speaker)
        caption = result.get("caption", "")
        if caption:
            storage.update_attachment(attachment_id, {
                "ai_caption": caption,
                "caption_status": "completed",
            })
            logger.info(f"Caption generated for {attachment_id} via {result.get('backend')}")
        else:
            storage.update_attachment(attachment_id, {"caption_status": "failed"})
            logger.warning(f"Empty caption for {attachment_id}")
    except Exception as e:
        storage.update_attachment(attachment_id, {"caption_status": "failed"})
        logger.error(f"Caption generation failed for {attachment_id}: {e}")


def _find_session_info(conference_id: str, session_id: str):
    """세션 정보(제목, 연자) 조회"""
    if not conference_id or not session_id:
        return "", ""
    conf = storage.get_conference(conference_id)
    if not conf:
        return "", ""
    for day in conf.get("days", []):
        for sess in day.get("sessions", []):
            if sess["id"] == session_id:
                return sess.get("title", ""), sess.get("speaker") or ""
    return "", ""


@router.post("/{attachment_id}/caption")
async def generate_single_caption(
    attachment_id: str,
    background_tasks: BackgroundTasks,
):
    """단일 이미지 캡션 생성 (수동 트리거)"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")

    if att.get("file_type") != "image":
        raise HTTPException(status_code=400, detail="이미지 파일만 캡션 생성 가능")

    session_title, speaker = _find_session_info(
        att.get("conference_id", ""), att.get("session_id", "")
    )

    background_tasks.add_task(
        _generate_caption_task,
        attachment_id,
        att["file_path"],
        session_title,
        speaker,
    )

    return {"message": "Caption generation started", "attachment_id": attachment_id}


@router.post("/sessions/{session_id}/captions")
async def generate_session_captions(
    session_id: str,
    background_tasks: BackgroundTasks,
    conference_id: str = Form(None),
):
    """세션의 모든 이미지에 대해 일괄 캡션 생성"""
    attachments = storage.get_attachments(session_id=session_id)
    image_atts = [a for a in attachments if a.get("file_type") == "image"]

    if not image_atts:
        return {"message": "No images found", "total": 0}

    # conference_id 추론
    conf_id = conference_id or image_atts[0].get("conference_id", "")
    session_title, speaker = _find_session_info(conf_id, session_id)

    for att in image_atts:
        background_tasks.add_task(
            _generate_caption_task,
            att["id"],
            att["file_path"],
            session_title,
            speaker,
        )

    logger.info(f"Queued {len(image_atts)} caption tasks for session {session_id}")
    return {
        "message": f"{len(image_atts)}개 이미지 캡션 생성 시작",
        "total": len(image_atts),
        "session_id": session_id,
    }


@router.get("/caption-status")
async def get_caption_status(conference_id: str = Query(..., description="학회 ID")):
    """캡션 생성 현황 조회"""
    attachments = storage.get_attachments_by_conference(conference_id)
    image_atts = [a for a in attachments if a.get("file_type") == "image"]

    total = len(image_atts)
    completed = sum(1 for a in image_atts if a.get("caption_status") == "completed")
    pending = sum(1 for a in image_atts if a.get("caption_status") == "pending")
    failed = sum(1 for a in image_atts if a.get("caption_status") == "failed")
    none_count = sum(1 for a in image_atts if not a.get("caption_status") or a.get("caption_status") == "none")

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "none": none_count,
    }


@router.patch("/{attachment_id}/caption")
async def update_caption(
    attachment_id: str,
    caption: str = Body(..., embed=True),
):
    """캡션 수동 수정"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")

    updated = storage.update_attachment(attachment_id, {
        "ai_caption": caption,
        "caption_status": "completed",
    })
    logger.info(f"Caption updated manually for {attachment_id}")
    return updated


@router.patch("/{attachment_id}/session")
async def reassign_session(
    attachment_id: str,
    session_id: str = Body(..., embed=True),
):
    """첨부파일의 세션 할당 변경 (사용자 수동 수정)"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")

    # "null" 문자열이면 None으로 변환 (미분류로 이동)
    target_session = None if session_id == "null" else session_id

    updated = storage.update_attachment(attachment_id, {
        "session_id": target_session,
        "match_confidence": "manual",
    })
    logger.info(f"Reassigned attachment {attachment_id} to session {target_session}")
    return updated


@router.get("/{attachment_id}")
async def get_attachment(attachment_id: str):
    """특정 첨부파일 메타데이터 조회"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")
    return att


@router.get("/{attachment_id}/file")
async def serve_attachment_file(attachment_id: str):
    """첨부파일 원본 서빙 (이미지 미리보기용)"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")

    file_path = att.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    from fastapi.responses import FileResponse
    return FileResponse(file_path)


@router.get("/{attachment_id}/text")
async def get_extracted_text(attachment_id: str):
    """추출된 텍스트 조회"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")
    return {
        "attachment_id": attachment_id,
        "extracted_text": att.get("extracted_text", ""),
        "extraction_status": att.get("extraction_status", "pending"),
    }


@router.delete("/{attachment_id}")
async def delete_attachment(attachment_id: str):
    """첨부파일 삭제"""
    att = storage.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{attachment_id}' not found")

    # 실제 파일 삭제
    file_path = att.get("file_path", "")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    storage.delete_attachment(attachment_id)
    return {"message": f"Attachment '{attachment_id}' deleted", "deleted": True}
