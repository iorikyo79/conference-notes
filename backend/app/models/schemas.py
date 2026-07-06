"""Pydantic Schemas for Conference Notes API"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Session(BaseModel):
    """세션 정보"""
    id: str = Field(..., description="세션 고유 ID")
    day_date: str = Field(..., description="소속 일자 (YYYY-MM-DD)")
    title: str = Field(..., description="세션명")
    speaker: Optional[str] = Field(None, description="연자")
    start_time: Optional[str] = Field(None, description="시작 시간 (HH:MM)")
    end_time: Optional[str] = Field(None, description="종료 시간 (HH:MM)")
    room: Optional[str] = Field(None, description="장소/룸")
    category: Optional[str] = Field(None, description="세션 유형 (교육, 발표, 심포지엄 등)")


class ConferenceDay(BaseModel):
    """학회 일자"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    label: str = Field(..., description="표시명 (예: '7/3 (금) 교육프로그램')")
    sessions: List[Session] = Field(default_factory=list)


class Conference(BaseModel):
    """학회 정보"""
    id: str = Field(..., description="학회 고유 ID")
    name: str = Field(..., description="학회명")
    location: Optional[str] = Field(None, description="장소")
    start_date: str = Field(..., description="시작일 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료일 (YYYY-MM-DD)")
    days: List[ConferenceDay] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ConferenceCreate(BaseModel):
    """학회 생성 요청"""
    id: str = Field(..., description="학회 고유 ID (slug)")
    name: str = Field(..., description="학회명")
    location: Optional[str] = None
    start_date: str = Field(..., description="시작일 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료일 (YYYY-MM-DD)")
    days: List[ConferenceDay] = Field(default_factory=list)


class SessionCreate(BaseModel):
    """세션 생성 요청"""
    title: str = Field(..., description="세션명")
    speaker: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None
    category: Optional[str] = None


class Note(BaseModel):
    """개별 노트"""
    id: str = Field(..., description="노트 고유 ID")
    session_id: str = Field(..., description="소속 세션 ID")
    conference_id: str = Field(..., description="소속 학회 ID")
    content: str = Field("", description="마크다운 본문")
    tags: List[str] = Field(default_factory=list, description="사용자 태그")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    is_starred: bool = Field(False, description="중요 표시")


class NoteCreate(BaseModel):
    """노트 생성 요청"""
    session_id: str
    conference_id: str
    content: str = ""


class NoteUpdate(BaseModel):
    """노트 수정 요청 (부분 업데이트)"""
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    is_starred: Optional[bool] = None


class Attachment(BaseModel):
    """첨부 파일"""
    id: str = Field(..., description="첨부파일 고유 ID")
    session_id: Optional[str] = Field(None, description="연결된 세션")
    conference_id: Optional[str] = Field(None, description="연결된 학회")
    filename: str = Field(..., description="원본 파일명")
    file_path: str = Field(..., description="저장 경로")
    file_type: str = Field(..., description="파일 유형 (pdf, image, etc)")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    extracted_text: Optional[str] = Field(None, description="추출된 텍스트")
    extraction_status: str = Field("pending", description="추출 상태 (pending, processing, completed, failed)")
    exif_datetime: Optional[datetime] = Field(None, description="EXIF 촬영 시간")
    match_confidence: str = Field("none", description="세션 매칭 신뢰도 (exact, tolerance, manual, none)")
    ai_caption: Optional[str] = Field(None, description="AI 생성 슬라이드 캡션")
    caption_status: str = Field("none", description="캡션 생성 상태 (none, pending, completed, failed)")
    uploaded_at: datetime = Field(default_factory=datetime.now)


class ReportRequest(BaseModel):
    """리포트 생성 요청"""
    conference_id: str
    session_ids: Optional[List[str]] = Field(None, description="특정 세션만 (없으면 전체)")
    report_type: str = Field("summary", description="리포트 유형 (summary, keywords, full)")


class SessionSummary(BaseModel):
    """세션별 요약"""
    session_id: str
    session_title: str
    summary: str = Field("", description="요약 텍스트")
    keywords: List[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """리포트 생성 응답"""
    conference_id: str
    conference_name: str
    report_type: str
    summary: str = Field("", description="전체 요약 마크다운")
    keywords: List[str] = Field(default_factory=list)
    session_summaries: List[SessionSummary] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
