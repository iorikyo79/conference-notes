"""PDF Text Extraction Service"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFExtractor:
    """PyMuPDF를 사용한 PDF 텍스트 추출"""

    def __init__(self):
        self._available = False
        try:
            import fitz  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("PyMuPDF (fitz) not installed. PDF extraction disabled.")

    def is_available(self) -> bool:
        """PDF 추출 가능 여부"""
        return self._available

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        PDF 파일에서 텍스트 추출

        Args:
            file_path: PDF 파일 경로

        Returns:
            추출된 텍스트 (실패 시 None)
        """
        if not self._available:
            logger.error("PyMuPDF not available")
            return None

        try:
            import fitz
            doc = fitz.open(file_path)
            text_parts = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")

            doc.close()

            if not text_parts:
                logger.info(f"No text found in PDF: {file_path}")
                return ""

            result = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(result)} chars from PDF: {file_path}")
            return result

        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {e}")
            return None
