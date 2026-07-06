"""Reports API Routes - Zhipu GLM 연동 + HTML 통합 리포트"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.schemas import ReportRequest
from app.services.storage import storage
from app.services.llm_service import llm_service
from app.services.html_report_generator import html_report_generator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """리포트 생성 (AI 요약 or HTML 통합)"""

    conf = storage.get_conference(request.conference_id)
    if not conf:
        raise HTTPException(
            status_code=404,
            detail=f"Conference '{request.conference_id}' not found"
        )

    # 학회의 모든 세션 수집
    sessions = []
    for day in conf.get("days", []):
        sessions.extend(day.get("sessions", []))

    # 특정 세션만 필터링
    if request.session_ids:
        sessions = [s for s in sessions if s["id"] in request.session_ids]

    # 세션별 노트와 첨부파일 수집
    notes = storage.get_notes_by_conference(request.conference_id)
    attachments = storage.get_attachments_by_conference(request.conference_id)

    # === HTML 통합 리포트 (AI 없음) ===
    if request.report_type == "html":
        html_content = html_report_generator.generate(
            conference=conf,
            sessions=sessions,
            notes=notes,
            attachments=attachments,
        )

        report_data = {
            "conference_id": request.conference_id,
            "conference_name": conf["name"],
            "report_type": "html",
            "summary": html_content,
            "keywords": [],
            "session_summaries": [],
            "generated_at": datetime.now().isoformat(),
            "llm_status": "not_required",
            "note_count": len([n for n in notes if n.get("content", "").strip()]),
            "html_content": html_content,
        }

        storage.save_report(report_data)
        logger.info(f"Generated HTML report for {request.conference_id}: {len(html_content)} chars")
        return report_data

    # === 기존 AI 요약 리포트 (summary / full) ===
    session_summaries = []
    all_keywords = []

    for session in sessions:
        session_notes = [n for n in notes if n.get("session_id") == session["id"]]
        session_attachments = [a for a in attachments if a.get("session_id") == session["id"]]

        if not session_notes and not session_attachments:
            continue

        notes_text = "\n\n".join([n.get("content", "") for n in session_notes])
        extracted_texts = [
            a.get("extracted_text", "") for a in session_attachments
            if a.get("extracted_text")
        ]

        result = llm_service.summarize_session(
            notes_text=notes_text,
            extracted_texts=extracted_texts,
            session_title=session["title"],
            speaker=session.get("speaker"),
        )

        session_summaries.append({
            "session_id": session["id"],
            "session_title": session["title"],
            "summary": result["summary"],
            "keywords": result["keywords"],
        })
        all_keywords.extend(result["keywords"])

    # 노트가 있는데 세션에 매핑되지 않은 경우 (일반 노트)
    unmapped_notes = [n for n in notes if n.get("session_id") not in [s["id"] for s in sessions]]
    if unmapped_notes:
        notes_text = "\n\n".join([n.get("content", "") for n in unmapped_notes])
        result = llm_service.summarize_session(
            notes_text=notes_text,
            extracted_texts=[],
            session_title="일반 메모",
        )
        session_summaries.append({
            "session_id": "general",
            "session_title": "일반 메모",
            "summary": result["summary"],
            "keywords": result["keywords"],
        })
        all_keywords.extend(result["keywords"])

    # 전체 리포트 생성
    if session_summaries:
        full_summary = llm_service.generate_full_report(session_summaries, conf["name"])
    else:
        full_summary = f"# {conf['name']} 참석 리포트\n\n작성된 노트가 없어 리포트를 생성할 수 없습니다."

    # 중복 키워드 제거 (빈도순)
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    unique_keywords = [kw for kw, _ in keyword_counts.most_common(20)]

    # LLM 사용 가능 여부 표시
    llm_status = "enabled" if llm_service.is_available() else "fallback"

    report_data = {
        "conference_id": request.conference_id,
        "conference_name": conf["name"],
        "report_type": request.report_type,
        "summary": full_summary,
        "keywords": unique_keywords,
        "session_summaries": session_summaries,
        "generated_at": datetime.now().isoformat(),
        "llm_status": llm_status,
        "note_count": len(notes),
    }

    # 리포트 저장
    storage.save_report(report_data)

    logger.info(
        f"Generated report for {request.conference_id}: "
        f"{len(session_summaries)} sessions, {len(notes)} notes, LLM={llm_status}"
    )

    return report_data


@router.get("/{conference_id}")
async def get_report(conference_id: str):
    """저장된 리포트 조회"""
    report = storage.get_report(conference_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report for conference '{conference_id}' not found. Generate one first via POST /api/reports/generate"
        )
    return report


@router.get("/{conference_id}/export")
async def export_report(conference_id: str, format: str = "md"):
    """리포트 내보내기 (마크다운 or HTML)"""
    report = storage.get_report(conference_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report for conference '{conference_id}' not found"
        )

    if format == "md":
        from fastapi.responses import PlainTextResponse
        from urllib.parse import quote
        filename = f"{report.get('conference_name', 'conference')}_report.md"
        encoded_filename = quote(filename)
        return PlainTextResponse(
            content=report.get("summary", ""),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
    elif format == "html":
        from fastapi import Response
        # HTML 리포트가 저장되어 있으면 그것을 반환, 없으면 즉시 생성
        if report.get("html_content"):
            html_content = report["html_content"]
        elif report.get("report_type") == "html":
            html_content = report.get("summary", "")
        else:
            # 기존 리포트를 HTML로 변환하여 생성
            conf = storage.get_conference(conference_id)
            if not conf:
                raise HTTPException(status_code=404, detail="Conference not found")
            sessions = []
            for day in conf.get("days", []):
                sessions.extend(day.get("sessions", []))
            notes = storage.get_notes_by_conference(conference_id)
            attachments = storage.get_attachments_by_conference(conference_id)
            html_content = html_report_generator.generate(conf, sessions, notes, attachments)

        filename = f"{report.get('conference_name', 'conference')}_report.html"
        # 파일명이 한글일 수 있으므로 RFC 5987 인코딩 사용
        from urllib.parse import quote
        encoded_filename = quote(filename)
        return Response(
            content=html_content.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use 'md' or 'html'.")
