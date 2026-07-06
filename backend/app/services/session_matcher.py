"""Session Matching Service - EXIF 시간 기반 세션 자동 매칭."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_TOLERANCE_MINUTES = 5


class SessionMatchResult:
    """이미지-세션 매칭 결과."""

    def __init__(
        self,
        session_id: Optional[str],
        confidence: str,  # "exact" | "tolerance" | "none"
        exif_datetime: Optional[datetime] = None,
        matched_session: Optional[Dict] = None,
        reason: str = "",
    ):
        self.session_id = session_id
        self.confidence = confidence
        self.exif_datetime = exif_datetime
        self.matched_session = matched_session
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "confidence": self.confidence,
            "exif_datetime": self.exif_datetime.isoformat() if self.exif_datetime else None,
            "session_title": self.matched_session.get("title") if self.matched_session else None,
            "session_speaker": self.matched_session.get("speaker") if self.matched_session else None,
            "reason": self.reason,
        }


class SessionMatcherService:
    """EXIF 시간 기반 세션 매칭."""

    def __init__(self, tolerance_minutes: int = DEFAULT_TOLERANCE_MINUTES):
        self._tolerance = timedelta(minutes=tolerance_minutes)

    def match(
        self,
        exif_datetime: Optional[datetime],
        conference: Optional[Dict],
    ) -> SessionMatchResult:
        """
        EXIF datetime을 학회 세션 시간표와 매칭.

        매칭 우선순위:
        1. exact: 세션 시간 범위 안에 포함
        2. tolerance: ±tolerance 내에 포함
        3. none: 매칭되는 세션 없음

        병렬 세션(동시간대 2개 이상)은 세션 중앙 시각에 가장 가까운 쪽 선택.
        """
        if not exif_datetime:
            return SessionMatchResult(
                session_id=None,
                confidence="none",
                reason="EXIF 시간 정보 없음",
            )

        if not conference:
            return SessionMatchResult(
                session_id=None,
                confidence="none",
                exif_datetime=exif_datetime,
                reason="학회 정보 없음",
            )

        img_date_str = exif_datetime.strftime("%Y-%m-%d")

        candidates_exact = []
        candidates_tolerance = []

        for day in conference.get("days", []):
            if day.get("date") != img_date_str:
                continue

            for session in day.get("sessions", []):
                start_str = session.get("start_time")
                end_str = session.get("end_time")
                if not start_str:
                    continue

                try:
                    start_time = datetime.strptime(start_str, "%H:%M").time()
                except ValueError:
                    continue

                session_start = datetime.combine(exif_datetime.date(), start_time)

                if end_str:
                    try:
                        end_time = datetime.strptime(end_str, "%H:%M").time()
                        session_end = datetime.combine(exif_datetime.date(), end_time)
                    except ValueError:
                        session_end = session_start + timedelta(hours=1)
                else:
                    session_end = session_start + timedelta(hours=1)

                if session_start <= exif_datetime <= session_end:
                    candidates_exact.append(
                        (session, self._distance_to_center(exif_datetime, session_start, session_end))
                    )
                elif (session_start - self._tolerance) <= exif_datetime <= (session_end + self._tolerance):
                    candidates_tolerance.append(
                        (session, self._distance_to_center(exif_datetime, session_start, session_end))
                    )

        if candidates_exact:
            candidates_exact.sort(key=lambda x: x[1])
            best = candidates_exact[0][0]
            return SessionMatchResult(
                session_id=best["id"],
                confidence="exact",
                exif_datetime=exif_datetime,
                matched_session=best,
                reason="세션 시간 범위 내",
            )

        if candidates_tolerance:
            candidates_tolerance.sort(key=lambda x: x[1])
            best = candidates_tolerance[0][0]
            return SessionMatchResult(
                session_id=best["id"],
                confidence="tolerance",
                exif_datetime=exif_datetime,
                matched_session=best,
                reason=f"±{self._tolerance.total_seconds() / 60:.0f}분 tolerance 내",
            )

        return SessionMatchResult(
            session_id=None,
            confidence="none",
            exif_datetime=exif_datetime,
            reason="해당 시간대 세션 없음",
        )

    @staticmethod
    def _distance_to_center(dt: datetime, start: datetime, end: datetime) -> float:
        """세션 중앙 시각으로부터의 거리 (초)."""
        center = start + (end - start) / 2
        return abs((dt - center).total_seconds())


# 전역 인스턴스
session_matcher = SessionMatcherService(tolerance_minutes=DEFAULT_TOLERANCE_MINUTES)
