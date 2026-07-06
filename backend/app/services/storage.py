"""JSON File-based Storage Service (학회별 분리 구조)"""
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
    """JSON 파일 기반 데이터 저장소 (학회별 디렉토리 분리)

    디렉토리 구조:
        storage/
        ├── data/
        │   └── conferences.json          학회 마스터 목록 (ID 배열)
        └── conferences/
            └── {conference_id}/
                ├── conference.json       학회 메타데이터 + 세션 일정
                ├── notes.json            해당 학회 노트
                ├── attachments.json      해당 학회 첨부파일 메타데이터
                ├── reports/
                │   └── html_report.html  HTML 리포트 (독립 파일)
                └── uploads/              원본 이미지 파일
    """

    def __init__(self):
        self._data_dir = Path(settings.DATA_DIR)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._conferences_root = Path(settings.CONFERENCES_DIR)
        self._conferences_root.mkdir(parents=True, exist_ok=True)

        self._conferences_index_path = self._data_dir / "conferences.json"

        self._lock = Lock()

        # 마스터 학회 목록 파일 초기화
        if not self._conferences_index_path.exists():
            self._write_json(self._conferences_index_path, [])

    # === Low-level JSON I/O ===

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
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp_path.replace(path)

    @staticmethod
    def generate_id() -> str:
        """UUID 생성"""
        return str(uuid.uuid4())

    # === 학회별 디렉토리 경로 ===

    def _conf_dir(self, conference_id: str) -> Path:
        """학회 디렉토리 경로"""
        return self._conferences_root / conference_id

    def _conf_file(self, conference_id: str) -> Path:
        """학회 메타데이터 파일 경로"""
        return self._conf_dir(conference_id) / "conference.json"

    def _notes_file(self, conference_id: str) -> Path:
        """학회 노트 파일 경로"""
        return self._conf_dir(conference_id) / "notes.json"

    def _attachments_file(self, conference_id: str) -> Path:
        """학회 첨부파일 메타데이터 파일 경로"""
        return self._conf_dir(conference_id) / "attachments.json"

    def _uploads_dir(self, conference_id: str) -> Path:
        """학회 업로드 디렉토리 경로"""
        return self._conf_dir(conference_id) / "uploads"

    def _reports_dir(self, conference_id: str) -> Path:
        """학회 리포트 디렉토리 경로"""
        return self._conf_dir(conference_id) / "reports"

    def _ensure_conf_dirs(self, conference_id: str) -> None:
        """학회 디렉토리 구조 생성"""
        self._conf_dir(conference_id).mkdir(parents=True, exist_ok=True)
        self._uploads_dir(conference_id).mkdir(parents=True, exist_ok=True)
        self._reports_dir(conference_id).mkdir(parents=True, exist_ok=True)

    # === Conference CRUD ===

    def get_conferences(self) -> List[Dict]:
        """전체 학회 목록 조회"""
        index = self._read_json(self._conferences_index_path)
        result = []
        for conf_id in index:
            conf_file = self._conf_file(conf_id)
            if conf_file.exists():
                result.append(self._read_json(conf_file))
            else:
                logger.warning(f"Conference file missing for {conf_id}")
        return result

    def get_conference(self, conference_id: str) -> Optional[Dict]:
        """특정 학회 조회"""
        conf_file = self._conf_file(conference_id)
        if conf_file.exists():
            return self._read_json(conf_file)
        return None

    def save_conference(self, conference: Dict) -> Dict:
        """학회 생성 또는 업데이트"""
        conf_id = conference["id"]

        # 디렉토리 구조 보장
        self._ensure_conf_dirs(conf_id)

        # 학회 메타데이터 저장
        self._write_json(self._conf_file(conf_id), conference)

        # 마스터 인덱스 업데이트
        index = self._read_json(self._conferences_index_path)
        if conf_id not in index:
            index.append(conf_id)
            self._write_json(self._conferences_index_path, index)

        # 빈 notes.json / attachments.json 초기화 (신규 학회인 경우)
        notes_path = self._notes_file(conf_id)
        if not notes_path.exists():
            self._write_json(notes_path, [])
        att_path = self._attachments_file(conf_id)
        if not att_path.exists():
            self._write_json(att_path, [])

        return conference

    def add_session_to_conference(
        self, conference_id: str, day_date: str, session: Dict
    ) -> Optional[Dict]:
        """학회의 특정 일자에 세션 추가"""
        conf = self.get_conference(conference_id)
        if not conf:
            return None

        for day in conf.get("days", []):
            if day["date"] == day_date:
                day.setdefault("sessions", []).append(session)
                self._write_json(self._conf_file(conference_id), conf)
                return conf
        return None

    def delete_session_from_conference(
        self, conference_id: str, session_id: str
    ) -> Optional[Dict]:
        """학회에서 특정 세션 삭제 (연관 노트도 함께 삭제)"""
        conf = self.get_conference(conference_id)
        if not conf:
            return None

        for day in conf.get("days", []):
            sessions = day.get("sessions", [])
            original_len = len(sessions)
            day["sessions"] = [s for s in sessions if s.get("id") != session_id]
            if len(day["sessions"]) < original_len:
                self._write_json(self._conf_file(conference_id), conf)

                # 연관 노트 삭제
                notes_path = self._notes_file(conference_id)
                if notes_path.exists():
                    notes = self._read_json(notes_path)
                    notes = [n for n in notes if n.get("session_id") != session_id]
                    self._write_json(notes_path, notes)
                return conf
        return None

    # === Note CRUD ===

    def get_notes(self, session_id: Optional[str] = None) -> List[Dict]:
        """노트 목록 조회 (세션 필터링 가능) - 전체 학회에서 검색"""
        all_notes = []
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            notes_path = self._notes_file(conf_id)
            if notes_path.exists():
                all_notes.extend(self._read_json(notes_path))

        if session_id:
            all_notes = [n for n in all_notes if n.get("session_id") == session_id]

        all_notes.sort(
            key=lambda n: n.get("updated_at") or n.get("created_at") or "",
            reverse=True,
        )
        return all_notes

    def get_notes_by_conference(self, conference_id: str) -> List[Dict]:
        """학회별 노트 목록"""
        notes_path = self._notes_file(conference_id)
        if not notes_path.exists():
            return []
        return self._read_json(notes_path)

    def get_note(self, note_id: str) -> Optional[Dict]:
        """특정 노트 조회 (전체 학회에서 검색)"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            notes_path = self._notes_file(conf_id)
            if notes_path.exists():
                notes = self._read_json(notes_path)
                for note in notes:
                    if note["id"] == note_id:
                        return note
        return None

    def save_note(self, note: Dict) -> Dict:
        """노트 생성 또는 업데이트"""
        conf_id = note.get("conference_id")
        if not conf_id:
            raise ValueError("Note must have conference_id")

        notes_path = self._notes_file(conf_id)
        notes = self._read_json(notes_path) if notes_path.exists() else []

        existing_idx = None
        for i, n in enumerate(notes):
            if n["id"] == note["id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            notes[existing_idx] = note
        else:
            notes.append(note)

        self._write_json(notes_path, notes)
        return note

    def update_note(self, note_id: str, updates: Dict) -> Optional[Dict]:
        """노트 부분 업데이트"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            notes_path = self._notes_file(conf_id)
            if not notes_path.exists():
                continue
            notes = self._read_json(notes_path)
            for i, n in enumerate(notes):
                if n["id"] == note_id:
                    n.update(updates)
                    n["updated_at"] = datetime.now().isoformat()
                    notes[i] = n
                    self._write_json(notes_path, notes)
                    return n
        return None

    def delete_note(self, note_id: str) -> bool:
        """노트 삭제"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            notes_path = self._notes_file(conf_id)
            if not notes_path.exists():
                continue
            notes = self._read_json(notes_path)
            original_len = len(notes)
            notes = [n for n in notes if n["id"] != note_id]
            if len(notes) < original_len:
                self._write_json(notes_path, notes)
                return True
        return False

    def delete_empty_notes(self, conference_id: Optional[str] = None) -> List[str]:
        """빈 노트 일괄 삭제"""
        deleted_ids = []

        if conference_id:
            conf_ids = [conference_id]
        else:
            conf_ids = self._read_json(self._conferences_index_path)

        for cid in conf_ids:
            notes_path = self._notes_file(cid)
            if not notes_path.exists():
                continue
            notes = self._read_json(notes_path)
            empty = [n for n in notes if not (n.get("content") or "").strip()]
            deleted_ids.extend(n["id"] for n in empty)
            remaining = [n for n in notes if (n.get("content") or "").strip()]
            if len(remaining) < len(notes):
                self._write_json(notes_path, remaining)

        return deleted_ids

    # === Attachment CRUD ===

    def get_attachments(self, session_id: Optional[str] = None) -> List[Dict]:
        """첨부파일 목록 조회 (전체 학회에서 검색)"""
        all_atts = []
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            att_path = self._attachments_file(conf_id)
            if att_path.exists():
                all_atts.extend(self._read_json(att_path))

        if session_id:
            all_atts = [a for a in all_atts if a.get("session_id") == session_id]
        return all_atts

    def get_attachments_by_conference(self, conference_id: str) -> List[Dict]:
        """학회별 첨부파일 목록"""
        att_path = self._attachments_file(conference_id)
        if not att_path.exists():
            return []
        return self._read_json(att_path)

    def get_attachment(self, attachment_id: str) -> Optional[Dict]:
        """특정 첨부파일 조회"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            att_path = self._attachments_file(conf_id)
            if not att_path.exists():
                continue
            atts = self._read_json(att_path)
            for att in atts:
                if att["id"] == attachment_id:
                    return att
        return None

    def save_attachment(self, attachment: Dict) -> Dict:
        """첨부파일 메타데이터 저장"""
        conf_id = attachment.get("conference_id")
        if not conf_id:
            raise ValueError("Attachment must have conference_id")

        att_path = self._attachments_file(conf_id)
        atts = self._read_json(att_path) if att_path.exists() else []

        existing_idx = None
        for i, a in enumerate(atts):
            if a["id"] == attachment["id"]:
                existing_idx = i
                break

        if existing_idx is not None:
            atts[existing_idx] = attachment
        else:
            atts.append(attachment)

        self._write_json(att_path, atts)
        return attachment

    def update_attachment(self, attachment_id: str, updates: Dict) -> Optional[Dict]:
        """첨부파일 업데이트"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            att_path = self._attachments_file(conf_id)
            if not att_path.exists():
                continue
            atts = self._read_json(att_path)
            for i, a in enumerate(atts):
                if a["id"] == attachment_id:
                    a.update(updates)
                    atts[i] = a
                    self._write_json(att_path, atts)
                    return a
        return None

    def delete_attachment(self, attachment_id: str) -> bool:
        """첨부파일 메타데이터 삭제"""
        index = self._read_json(self._conferences_index_path)
        for conf_id in index:
            att_path = self._attachments_file(conf_id)
            if not att_path.exists():
                continue
            atts = self._read_json(att_path)
            original_len = len(atts)
            atts = [a for a in atts if a["id"] != attachment_id]
            if len(atts) < original_len:
                self._write_json(att_path, atts)
                return True
        return False

    def get_upload_dir(self, conference_id: str) -> Path:
        """학회별 업로드 디렉토리 경로 반환 (파일 저장용)"""
        self._ensure_conf_dirs(conference_id)
        return self._uploads_dir(conference_id)

    # === Report Storage ===

    def get_report(self, conference_id: str) -> Optional[Dict]:
        """저장된 HTML 리포트 조회"""
        report_file = self._reports_dir(conference_id) / "html_report.html"
        if not report_file.exists():
            return None

        content = report_file.read_text(encoding="utf-8")
        return {
            "conference_id": conference_id,
            "report_type": "html",
            "html_content": content,
            "generated_at": datetime.fromtimestamp(
                report_file.stat().st_mtime
            ).isoformat(),
        }

    def save_report(self, report: Dict) -> Dict:
        """HTML 리포트를 파일로 저장"""
        conf_id = report.get("conference_id")
        if not conf_id:
            raise ValueError("Report must have conference_id")

        self._ensure_conf_dirs(conf_id)
        report_file = self._reports_dir(conf_id) / "html_report.html"

        html_content = report.get("html_content") or report.get("summary", "")
        report_file.write_text(html_content, encoding="utf-8")

        logger.info(f"HTML report saved: {report_file} ({len(html_content)} chars)")
        return {
            "conference_id": conf_id,
            "report_type": report.get("report_type", "html"),
            "generated_at": datetime.now().isoformat(),
        }


# 전역 인스턴스
storage = StorageService()
