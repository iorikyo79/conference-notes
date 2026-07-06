"""EXIF Metadata Extraction Service"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ExifService:
    """Pillow을 사용한 이미지 EXIF 메타데이터 추출"""

    # EXIF tag IDs
    DATETIME_ORIGINAL = 36867  # DateTimeOriginal
    DATETIME = 306             # DateTime (modification)

    def __init__(self):
        self._available = False
        try:
            from PIL import Image  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("Pillow not installed. EXIF extraction disabled.")

    def is_available(self) -> bool:
        return self._available

    def extract_datetime(self, file_path: str) -> Optional[datetime]:
        """
        이미지 파일에서 DateTimeOriginal EXIF 메타데이터 추출.

        Returns:
            datetime object or None if no EXIF datetime found.
        """
        if not self._available:
            return None

        try:
            from PIL import Image

            with Image.open(file_path) as image:
                exif_data = image.getexif()
                if not exif_data:
                    return None

                # DateTimeOriginal 우선, DateTime으로 fallback
                datetime_str = exif_data.get(self.DATETIME_ORIGINAL)
                if not datetime_str:
                    datetime_str = exif_data.get(self.DATETIME)

                if not datetime_str:
                    return None

                # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                try:
                    return datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Unparseable EXIF datetime: {datetime_str}")
                    return None

        except Exception as e:
            logger.error(f"EXIF extraction failed for {file_path}: {e}")
            return None


# 전역 인스턴스
exif_service = ExifService()
