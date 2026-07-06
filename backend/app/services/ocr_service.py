"""OCR Service for Image Text Extraction"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCRService:
    """Tesseract OCR을 사용한 이미지 텍스트 추출"""

    def __init__(self, lang: str = "kor+eng"):
        """
        Args:
            lang: OCR 언어 (기본: 한국어+영어)
        """
        self._lang = lang
        self._available = False
        try:
            import pytesseract  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("pytesseract not installed. OCR disabled.")

    def is_available(self) -> bool:
        """OCR 사용 가능 여부"""
        if not self._available:
            return False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            logger.warning("Tesseract binary not found. Install: brew install tesseract tesseract-lang")
            return False

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        이미지 파일에서 텍스트 추출

        Args:
            file_path: 이미지 파일 경로

        Returns:
            추출된 텍스트 (실패 시 None)
        """
        if not self.is_available():
            logger.error("OCR not available")
            return None

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang=self._lang)

            result = text.strip()
            logger.info(f"OCR extracted {len(result)} chars from: {file_path}")
            return result

        except Exception as e:
            logger.error(f"OCR failed for {file_path}: {e}")
            return None
