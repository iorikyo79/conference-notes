"""HTML Report Generator - 노트 + 슬라이드 이미지 + 캡션을 통합한 HTML 리포트 생성."""
import base64
import html
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import markdown as md

logger = logging.getLogger(__name__)


class HTMLReportGenerator:
    """AI 없이 노트(md) + 이미지 + 캡션을 조합하여 HTML 리포트 생성."""

    def generate(
        self,
        conference: Dict,
        sessions: List[Dict],
        notes: List[Dict],
        attachments: List[Dict],
    ) -> str:
        """
        전체 HTML 리포트 생성.

        Args:
            conference: 학회 정보
            sessions: 세션 목록 (시간순)
            notes: 노트 목록
            attachments: 첨부파일 목록

        Returns:
            완전한 HTML 문자열 (자체 완결형, 외부 의존성 없음)
        """
        conference_name = conference.get("name", "학회")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 세션별 데이터 구성
        session_sections = []
        toc_items = []

        for i, session in enumerate(sessions):
            session_id = session["id"]
            session_notes = [n for n in notes if n.get("session_id") == session_id]
            session_atts = [a for a in attachments if a.get("session_id") == session_id]
            image_atts = [a for a in session_atts if a.get("file_type") == "image"]

            if not session_notes and not image_atts:
                continue

            section_id = f"session-{i}"
            title = session.get("title", "제목 없음")
            speaker = session.get("speaker") or ""
            start_time = session.get("start_time") or ""
            end_time = session.get("end_time") or ""

            # 목차 항목
            toc_items.append(
                f'<li><a href="#{section_id}">{html.escape(title)}</a>'
                f'{" — " + html.escape(speaker) if speaker else ""}'
                f'{f" ({start_time}~{end_time})" if start_time else ""}</li>'
            )

            # 노트 내용 (마크다운 → HTML)
            notes_html = ""
            if session_notes:
                combined_notes = "\n\n".join(
                    n.get("content", "") for n in session_notes if n.get("content", "").strip()
                )
                if combined_notes.strip():
                    notes_html = md.markdown(combined_notes, extensions=["extra", "toc"])

            # 슬라이드 갤러리
            slides_html = self._build_slides_html(image_atts)

            section_html = self._build_section_html(
                section_id, title, speaker, start_time, end_time,
                notes_html, slides_html,
            )
            session_sections.append(section_html)

        # 미분류 노트/첨부파일
        unmapped_notes = [
            n for n in notes
            if n.get("session_id") not in [s["id"] for s in sessions]
            and n.get("content", "").strip()
        ]
        unmapped_atts = [
            a for a in attachments
            if a.get("session_id") not in [s["id"] for s in sessions]
            and a.get("file_type") == "image"
        ]
        if unmapped_notes or unmapped_atts:
            unmapped_notes_html = ""
            if unmapped_notes:
                combined = "\n\n".join(n.get("content", "") for n in unmapped_notes)
                unmapped_notes_html = md.markdown(combined, extensions=["extra"])
            unmapped_slides = self._build_slides_html(unmapped_atts)

            toc_items.append(f'<li><a href="#general">일반 메모</a></li>')
            session_sections.append(self._build_section_html(
                "general", "일반 메모", "", "", "",
                unmapped_notes_html, unmapped_slides,
            ))

        toc_html = "\n".join(toc_items)

        # 통계
        total_notes = len([n for n in notes if n.get("content", "").strip()])
        total_slides = len([a for a in attachments if a.get("file_type") == "image"])
        captioned = len([a for a in attachments if a.get("ai_caption")])

        full_html = self._build_full_html(
            conference_name, generated_at, toc_html,
            "\n".join(session_sections),
            total_notes, total_slides, captioned,
        )

        logger.info(
            f"Generated HTML report: {conference_name}, "
            f"{len(sessions)} sessions, {total_notes} notes, {total_slides} images"
        )

        return full_html

    @staticmethod
    def _build_slides_html(image_atts: List[Dict]) -> str:
        """슬라이드 갤러리 HTML 생성"""
        if not image_atts:
            return ""

        figures = []
        for att in image_atts:
            file_path = att.get("file_path", "")
            caption = att.get("ai_caption") or att.get("extracted_text") or ""
            filename = att.get("filename", "")

            # base64 인코딩
            img_src = ""
            if file_path and Path(file_path).exists():
                try:
                    with open(file_path, "rb") as f:
                        base64_img = base64.b64encode(f.read()).decode("utf-8")
                    ext = Path(file_path).suffix.lower().lstrip(".")
                    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
                    img_src = f"data:image/{mime};base64,{base64_img}"
                except Exception as e:
                    logger.warning(f"Failed to encode image {file_path}: {e}")

            if img_src:
                caption_html = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
                figures.append(
                    f'<figure class="slide">\n'
                    f'  <img src="{img_src}" alt="{html.escape(filename)}" loading="lazy" />\n'
                    f'  {caption_html}\n'
                    f'</figure>'
                )

        if not figures:
            return ""

        return f'<div class="slides">\n' + "\n".join(figures) + "\n</div>"

    @staticmethod
    def _build_section_html(
        section_id: str,
        title: str,
        speaker: str,
        start_time: str,
        end_time: str,
        notes_html: str,
        slides_html: str,
    ) -> str:
        """세션 섹션 HTML"""
        meta_parts = []
        if speaker:
            meta_parts.append(html.escape(speaker))
        if start_time:
            time_str = f"{start_time}~{end_time}" if end_time else start_time
            meta_parts.append(time_str)
        meta_html = f'<div class="session-meta">{" | ".join(meta_parts)}</div>' if meta_parts else ""

        notes_section = ""
        if notes_html:
            notes_section = f'<div class="notes">\n{notes_html}\n</div>'

        slides_section = ""
        if slides_html:
            slides_section = f'<h3 class="slides-heading">📸 발표 슬라이드</h3>\n{slides_html}'

        if not notes_section and not slides_section:
            return ""

        return f"""
<section id="{section_id}" class="session-section">
  <h2>{html.escape(title)}</h2>
  {meta_html}
  {notes_section}
  {slides_section}
</section>"""

    @staticmethod
    def _build_full_html(
        conference_name: str,
        generated_at: str,
        toc_html: str,
        sections_html: str,
        total_notes: int,
        total_slides: int,
        captioned: int,
    ) -> str:
        """완전한 HTML 문서 생성"""

        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(conference_name)} 참석 리포트</title>
  <style>
    :root {{
      --primary: #4a4af0;
      --bg: #f8f9fa;
      --card-bg: #ffffff;
      --text: #1a1a2e;
      --text-muted: #666;
      --border: #e0e0e8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif;
      line-height: 1.7;
      color: var(--text);
      background: var(--bg);
      max-width: 900px;
      margin: 0 auto;
      padding: 2rem 1rem;
    }}
    header {{
      text-align: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 2px solid var(--primary);
    }}
    header h1 {{
      font-size: 1.6rem;
      color: var(--text);
      margin-bottom: 0.5rem;
    }}
    .meta-info {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}
    .stats {{
      display: flex;
      justify-content: center;
      gap: 1.5rem;
      margin-top: 1rem;
      flex-wrap: wrap;
    }}
    .stats span {{
      font-size: 0.8rem;
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      background: var(--card-bg);
    }}
    nav {{
      background: var(--card-bg);
      border-radius: 10px;
      padding: 1rem 1.5rem;
      margin-bottom: 2rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    nav h3 {{
      font-size: 0.85rem;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
    }}
    nav ul {{ list-style: none; }}
    nav li {{ padding: 0.2rem 0; }}
    nav a {{
      color: var(--primary);
      text-decoration: none;
      font-size: 0.88rem;
    }}
    nav a:hover {{ text-decoration: underline; }}
    .session-section {{
      background: var(--card-bg);
      border-radius: 12px;
      padding: 1.5rem 2rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .session-section h2 {{
      font-size: 1.2rem;
      color: var(--text);
      margin-bottom: 0.25rem;
    }}
    .session-meta {{
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 1rem;
    }}
    .notes h1, .notes h2, .notes h3 {{
      font-size: 1rem;
      margin: 1rem 0 0.5rem;
      color: var(--text);
    }}
    .notes p {{ margin: 0.5rem 0; font-size: 0.9rem; }}
    .notes ul, .notes ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
    .notes li {{ font-size: 0.9rem; }}
    .notes code {{
      background: #f0f0f5;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 0.85rem;
    }}
    .notes pre {{
      background: #1a1a2e;
      color: #e0e0e8;
      padding: 0.75rem;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 0.82rem;
    }}
    .notes table {{
      border-collapse: collapse;
      width: 100%;
      margin: 0.5rem 0;
    }}
    .notes th, .notes td {{
      border: 1px solid var(--border);
      padding: 0.4rem 0.6rem;
      font-size: 0.85rem;
    }}
    .notes th {{ background: #f8f8fa; }}
    .notes blockquote {{
      border-left: 4px solid var(--primary);
      padding: 0.5rem 0.75rem 0.5rem 1rem;
      margin: 0.75rem 0;
      background: #f0f0ff;
      border-radius: 0 8px 8px 0;
      color: #333;
      font-size: 0.88rem;
    }}
    .slides-heading {{
      font-size: 0.9rem;
      margin: 1.5rem 0 0.75rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
    }}
    .slides {{
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}
    .slide {{
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      break-inside: avoid;
    }}
    .slide img {{
      width: 100%;
      display: block;
    }}
    .slide figcaption {{
      padding: 0.5rem 0.75rem;
      font-size: 0.8rem;
      color: var(--text-muted);
      background: #fafafa;
      border-top: 1px solid var(--border);
    }}
    footer {{
      text-align: center;
      padding: 2rem 0;
      color: var(--text-muted);
      font-size: 0.8rem;
    }}
    @media (max-width: 600px) {{
      body {{ padding: 1rem 0.5rem; }}
      .session-section {{ padding: 1rem; }}
    }}
    @media print {{
      body {{ background: white; max-width: none; }}
      .session-section {{ break-inside: avoid; box-shadow: none; border: 1px solid #ddd; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(conference_name)} 참석 리포트</h1>
    <div class="meta-info">생성일: {generated_at}</div>
    <div class="stats">
      <span>📝 노트 {total_notes}개</span>
      <span>🖼️ 슬라이드 {total_slides}개</span>
      <span>✨ 캡션 {captioned}개</span>
    </div>
  </header>

  <nav>
    <h3>목차</h3>
    <ul>
{chr(10).join(f"      {item}" for item in toc_html.split(chr(10)))}
    </ul>
  </nav>

{sections_html}

  <footer>
    본 리포트는 Conference Notes 시스템에 의해 자동 생성되었습니다.<br>
    {generated_at}
  </footer>
</body>
</html>"""


# 전역 인스턴스
html_report_generator = HTMLReportGenerator()
