"""JSON File-based Storage Service"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from threading import Lock

from app.config.settings import settings

logger = logging.getLogger(__name__)


class StorageService:
    """JSON 파일 기반 데이터 저장소

    MVP 단계에서 DB 없이 JSON 파일로 데이터를 영속화합니다.
    스레드 안전성을 위해 파일 접근 시 Lock을 사용합니다.
    """

    def __init__(self):
        self._data_dir = Path(settings.DATA_DIR)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._conferences_path = self._data_dir / "conferences.json"
        self._notes_path = self._data_dir / "notes.json"
        self._attachments_path = self._data_dir / "attachments.json"
        self._reports_path = self._data_dir / "reports.json"

        self._lock = Lock()

        # 파일이 없으면 빈 배열로 초기화
        for path in [
            self._conferences_path,
            self._notes_path,
            self._attachments_path,
            self._reports_path,
        ]:
            if not path.exists():
                self._write_json(path, [])

    def _read_json(self, path: Path) -> Any:
        """JSON 파일 읽기"""
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"Failed to read {path}: {e}, returning empty list")
                return []

    def _write_json(self, path: Path, data: Any) -> None:
        """JSON 파일 쓰기 (atomic write)"""
        with self._lock:
            tmp_path = path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp_path.replace(path)

    @staticmethod
    def generate_id() -> str:
        """UUID 생성"""
        return str(uuid.uuid4())

    # === Conference CRUD ===

    def get_conferences(self) -> List[Dict]:
        """전체 학회 목록 조회"""
        return self._read_json(self._conferences_path)

    def get_conference(self, conference_id: str) -> Optional[Dict]:
        """특정 학회 조회"""
        conferences = self.get_conferences()
        for conf in conferences:
            if conf["id"] == conference_id:
                return conf
        return None

    def save_conference(self, conference: Dict) -> Dict:
        """학회 생성 또는 업데이트"""
        conferences = self.get_conferences()
        # 기존에 있으면 업데이트, 없으면 추가
        existing_idx = None
        for i, c in enumerate(conferences):
            if c["id"] == conference["id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            conferences[existing_idx] = conference
        else:
            conferences.append(conference)

        self._write_json(self._conferences_path, conferences)
        return conference

    def add_session_to_conference(
        self, conference_id: str, day_date: str, session: Dict
    ) -> Optional[Dict]:
        """학회의 특정 일자에 세션 추가"""
        conferences = self.get_conferences()
        for conf in conferences:
            if conf["id"] == conference_id:
                for day in conf.get("days", []):
                    if day["date"] == day_date:
                        day.setdefault("sessions", []).append(session)
                        self._write_json(self._conferences_path, conferences)
                        return conf
                break
        return None

    def delete_session_from_conference(
        self, conference_id: str, session_id: str
    ) -> Optional[Dict]:
        """학회에서 특정 세션 삭제 (연관 노트도 함께 삭제)"""
        conferences = self.get_conferences()
        for conf in conferences:
            if conf["id"] == conference_id:
                for day in conf.get("days", []):
                    sessions = day.get("sessions", [])
                    original_len = len(sessions)
                    day["sessions"] = [
                        s for s in sessions if s.get("id") != session_id
                    ]
                    if len(day["sessions"]) < original_len:
                        self._write_json(self._conferences_path, conferences)
                        # 연관 노트 삭제
                        notes = self._read_json(self._notes_path)
                        notes = [
                            n for n in notes if n.get("session_id") != session_id
                        ]
                        self._write_json(self._notes_path, notes)
                        return conf
                break
        return None

    # === Note CRUD ===

    def get_notes(self, session_id: Optional[str] = None) -> List[Dict]:
        """노트 목록 조회 (세션 필터링 가능)"""
        notes = self._read_json(self._notes_path)
        if session_id:
            notes = [n for n in notes if n.get("session_id") == session_id]
        # 최신순 정렬
        notes.sort(key=lambda n: n.get("updated_at") or n.get("created_at") or "", reverse=True)
        return notes

    def get_notes_by_conference(self, conference_id: str) -> List[Dict]:
        """학회별 노트 목록"""
        notes = self._read_json(self._notes_path)
        return [n for n in notes if n.get("conference_id") == conference_id]

    def get_note(self, note_id: str) -> Optional[Dict]:
        """특정 노트 조회"""
        notes = self._read_json(self._notes_path)
        for note in notes:
            if note["id"] == note_id:
                return note
        return None

    def save_note(self, note: Dict) -> Dict:
        """노트 생성 또는 업데이트"""
        notes = self._read_json(self._notes_path)
        existing_idx = None
        for i, n in enumerate(notes):
            if n["id"] == note["id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            notes[existing_idx] = note
        else:
            notes.append(note)

        self._write_json(self._notes_path, notes)
        return note

    def update_note(self, note_id: str, updates: Dict) -> Optional[Dict]:
        """노트 부분 업데이트"""
        notes = self._read_json(self._notes_path)
        for i, n in enumerate(notes):
            if n["id"] == note_id:
                n.update(updates)
                n["updated_at"] = datetime.now().isoformat()
                notes[i] = n
                self._write_json(self._notes_path, notes)
                return n
        return None

    def delete_note(self, note_id: str) -> bool:
        """노트 삭제"""
        notes = self._read_json(self._notes_path)
        original_len = len(notes)
        notes = [n for n in notes if n["id"] != note_id]
        if len(notes) < original_len:
            self._write_json(self._notes_path, notes)
            return True
        return False

    # === Attachment CRUD ===

    def get_attachments(self, session_id: Optional[str] = None) -> List[Dict]:
        """첨부파일 목록 조회"""
        attachments = self._read_json(self._attachments_path)
        if session_id:
            attachments = [a for a in attachments if a.get("session_id") == session_id]
        return attachments

    def get_attachments_by_conference(self, conference_id: str) -> List[Dict]:
        """학회별 첨부파일 목록"""
        attachments = self._read_json(self._attachments_path)
        return [a for a in attachments if a.get("conference_id") == conference_id]

    def get_attachment(self, attachment_id: str) -> Optional[Dict]:
        """특정 첨부파일 조회"""
        attachments = self._read_json(self._attachments_path)
        for att in attachments:
            if att["id"] == attachment_id:
                return att
        return None

    def save_attachment(self, attachment: Dict) -> Dict:
        """첨부파일 메타데이터 저장"""
        attachments = self._read_json(self._attachments_path)
        existing_idx = None
        for i, a in enumerate(attachments):
            if a["id"] == attachment["id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            attachments[existing_idx] = attachment
        else:
            attachments.append(attachment)

        self._write_json(self._attachments_path, attachments)
        return attachment

    def update_attachment(self, attachment_id: str, updates: Dict) -> Optional[Dict]:
        """첨부파일 업데이트 (텍스트 추출 완료 후 등)"""
        attachments = self._read_json(self._attachments_path)
        for i, a in enumerate(attachments):
            if a["id"] == attachment_id:
                a.update(updates)
                attachments[i] = a
                self._write_json(self._attachments_path, attachments)
                return a
        return None

    def delete_attachment(self, attachment_id: str) -> bool:
        """첨부파일 삭제"""
        attachments = self._read_json(self._attachments_path)
        original_len = len(attachments)
        attachments = [a for a in attachments if a["id"] != attachment_id]
        if len(attachments) < original_len:
            self._write_json(self._attachments_path, attachments)
            return True
        return False

    # === Report Storage ===

    def get_report(self, conference_id: str) -> Optional[Dict]:
        """저장된 리포트 조회"""
        reports = self._read_json(self._reports_path)
        for r in reports:
            if r.get("conference_id") == conference_id:
                return r
        return None

    def save_report(self, report: Dict) -> Dict:
        """리포트 저장"""
        reports = self._read_json(self._reports_path)
        existing_idx = None
        for i, r in enumerate(reports):
            if r.get("conference_id") == report.get("conference_id"):
                existing_idx = i
                break

        if existing_idx is not None:
            reports[existing_idx] = report
        else:
            reports.append(report)

        self._write_json(self._reports_path, reports)
        return report


# 전역 인스턴스
storage = StorageService()
