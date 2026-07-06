"""HTML Report Generator - 인터랙티브 HTML 리포트 생성 (노트 + 슬라이드 + 캡션)."""
import base64
import html
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import markdown as md

logger = logging.getLogger(__name__)


class HTMLReportGenerator:
    """AI 없이 노트(md) + 이미지 + 캡션을 조합하여 인터랙티브 HTML 리포트 생성."""

    def generate(
        self,
        conference: Dict,
        sessions: List[Dict],
        notes: List[Dict],
        attachments: List[Dict],
    ) -> str:
        conference_name = conference.get("name", "학회")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        session_blocks = []
        toc_items = []

        for i, session in enumerate(sessions):
            session_id = session["id"]
            session_notes = [n for n in notes if n.get("session_id") == session_id]
            session_atts = [a for a in attachments if a.get("session_id") == session_id]
            image_atts = [a for a in session_atts if a.get("file_type") == "image"]

            if not session_notes and not image_atts:
                continue

            section_id = f"sec-{i}"
            title = session.get("title", "제목 없음")
            speaker = session.get("speaker") or ""
            start_time = session.get("start_time") or ""
            end_time = session.get("end_time") or ""

            toc_items.append({
                "id": section_id, "title": title, "speaker": speaker,
                "time": f"{start_time}~{end_time}" if end_time else start_time,
            })

            notes_html = ""
            if session_notes:
                combined = "\n\n".join(n.get("content", "") for n in session_notes if n.get("content", "").strip())
                if combined.strip():
                    notes_html = md.markdown(combined, extensions=["extra", "toc"])

            slide_count = len(image_atts)
            slides_html = self._build_slides_html(image_atts)

            session_blocks.append(self._build_section_html(
                section_id, title, speaker, start_time, end_time,
                notes_html, slides_html, slide_count,
            ))

        # 미분류
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
            toc_items.append({"id": "general", "title": "일반 메모", "speaker": "", "time": ""})
            session_blocks.append(self._build_section_html(
                "general", "일반 메모", "", "", "",
                unmapped_notes_html, unmapped_slides, len(unmapped_atts),
            ))

        # 목차 HTML
        toc_parts = []
        for item in toc_items:
            toc_parts.append(
                f'<a href="#{item["id"]}" class="toc-item">'
                f'<span class="toc-title">{html.escape(item["title"])}</span>'
                f'{f"<span class=\"toc-speaker\">{html.escape(item["speaker"])}</span>" if item["speaker"] else ""}'
                f'<span class="toc-time">{item["time"]}</span>'
                f'</a>'
            )
        toc_html = "\n".join(toc_parts)

        total_notes = len([n for n in notes if n.get("content", "").strip()])
        total_slides = len([a for a in attachments if a.get("file_type") == "image"])
        total_captioned = sum(1 for a in attachments if a.get("ai_caption"))
        total_sessions = len(session_blocks)

        full_html = self._build_full_html(
            conference_name, generated_at, toc_html,
            "\n".join(session_blocks),
            total_sessions, total_notes, total_slides, total_captioned,
        )

        logger.info(
            f"Generated interactive HTML report: {conference_name}, "
            f"{total_sessions} sessions, {total_notes} notes, {total_slides} images"
        )
        return full_html

    @staticmethod
    def _build_slides_html(image_atts: List[Dict]) -> str:
        if not image_atts:
            return ""

        figures = []
        for att in image_atts:
            file_path = att.get("file_path", "")
            caption = att.get("ai_caption") or att.get("extracted_text") or ""
            filename = att.get("filename", "")

            img_src = ""
            if file_path and Path(file_path).exists():
                try:
                    with open(file_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    ext = Path(file_path).suffix.lower().lstrip(".")
                    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
                    img_src = f"data:image/{mime};base64,{b64}"
                except Exception as e:
                    logger.warning(f"Failed to encode image {file_path}: {e}")

            if img_src:
                cap_html = f'<figcaption>{html.escape(caption)}</figcaption>' if caption else ""
                figures.append(
                    f'<figure class="slide-card">\n'
                    f'  <img src="{img_src}" alt="{html.escape(filename)}" loading="lazy" />\n'
                    f'  {cap_html}\n'
                    f'</figure>'
                )

        if not figures:
            return ""

        return "\n".join(figures)

    @staticmethod
    def _build_section_html(
        section_id: str,
        title: str,
        speaker: str,
        start_time: str,
        end_time: str,
        notes_html: str,
        slides_html: str,
        slide_count: int,
    ) -> str:
        meta_parts = []
        if speaker:
            meta_parts.append(html.escape(speaker))
        if start_time:
            time_str = f"{start_time}~{end_time}" if end_time else start_time
            meta_parts.append(time_str)
        meta_html = " · ".join(meta_parts)

        notes_section = ""
        if notes_html:
            notes_section = f'<div class="session-notes prose">\n      {notes_html}\n    </div>'

        slides_section = ""
        if slides_html:
            slides_section = f'''
    <div class="slides-section">
      <button class="slides-toggle" onclick="toggleSlides(this)">📸 발표 슬라이드 ({slide_count}장)</button>
      <div class="slides-grid" style="display:none;">
        {slides_html}
      </div>
    </div>'''

        if not notes_section and not slides_section:
            return ""

        return f'''
  <section id="{section_id}" class="session-section reveal">
    <div class="session-header">
      <h2>{html.escape(title)}</h2>
      <div class="session-meta">{meta_html}</div>
    </div>
    {notes_section}
    {slides_section}
  </section>'''

    @staticmethod
    def _build_full_html(
        conference_name: str,
        generated_at: str,
        toc_html: str,
        sections_html: str,
        total_sessions: int,
        total_notes: int,
        total_slides: int,
        captioned: int,
    ) -> str:
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(conference_name)} 참석 리포트</title>
  <style>
    :root {{
      --primary: #4a4af0;
      --primary-light: #e8e8ff;
      --primary-dark: #3a3ae0;
      --bg: #f0f0f5;
      --card-bg: #ffffff;
      --text: #1a1a2e;
      --text-muted: #6b7280;
      --border: #e5e7eb;
      --radius: 16px;
      --shadow: 0 4px 20px rgba(0,0,0,0.06);
      --shadow-hover: 0 8px 30px rgba(74,74,240,0.12);
      --transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif;
      line-height: 1.8; color: var(--text); background: var(--bg); overflow-x: hidden;
    }}

    /* Scroll Progress */
    #progress-bar {{
      position: fixed; top: 0; left: 0; height: 3px; width: 0%;
      background: linear-gradient(90deg, var(--primary), #a78bfa, var(--primary));
      background-size: 200% 100%; animation: shimmer 3s linear infinite;
      z-index: 1000; transition: width 0.1s ease-out;
    }}
    @keyframes shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}

    /* Hero */
    .hero {{
      min-height: 80vh; display: flex; flex-direction: column;
      justify-content: center; align-items: center; text-align: center;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      color: white; position: relative; overflow: hidden; padding: 2rem;
    }}
    .hero::before {{
      content: ''; position: absolute; width: 600px; height: 600px; border-radius: 50%;
      background: radial-gradient(circle, rgba(74,74,240,0.15) 0%, transparent 70%);
      top: -200px; right: -100px; animation: float 8s ease-in-out infinite;
    }}
    .hero::after {{
      content: ''; position: absolute; width: 400px; height: 400px; border-radius: 50%;
      background: radial-gradient(circle, rgba(167,139,250,0.15) 0%, transparent 70%);
      bottom: -100px; left: -100px; animation: float 10s ease-in-out infinite reverse;
    }}
    @keyframes float {{ 0%,100% {{ transform: translate(0,0); }} 50% {{ transform: translate(30px,30px); }} }}
    .hero-content {{ position: relative; z-index: 1; animation: fadeInUp 1s ease-out; }}
    .hero h1 {{
      font-size: clamp(1.5rem, 5vw, 2.8rem); margin-bottom: 1rem;
      background: linear-gradient(135deg, #fff 0%, #c7d2fe 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }}
    .hero-subtitle {{ font-size: 1rem; color: rgba(255,255,255,0.6); margin-bottom: 2rem; }}
    .hero-stats {{ display: flex; gap: 2rem; flex-wrap: wrap; justify-content: center; }}
    .hero-stat {{
      text-align: center; padding: 1rem 1.5rem;
      background: rgba(255,255,255,0.05); border-radius: var(--radius);
      border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px); transition: var(--transition);
    }}
    .hero-stat:hover {{ transform: translateY(-5px); background: rgba(255,255,255,0.1); }}
    .hero-stat-number {{ font-size: 1.8rem; font-weight: 700; color: #a78bfa; display: block; }}
    .hero-stat-label {{ font-size: 0.75rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 1px; }}
    .hero-scroll-hint {{
      position: absolute; bottom: 2rem; left: 50%; transform: translateX(-50%);
      color: rgba(255,255,255,0.4); animation: bounce 2s infinite;
    }}
    @keyframes bounce {{ 0%,100% {{ transform: translateX(-50%) translateY(0); }} 50% {{ transform: translateX(-50%) translateY(10px); }} }}

    /* TOC */
    .toc-container {{ max-width: 700px; margin: 3rem auto; padding: 0 1rem; }}
    .toc-container h3 {{
      text-align: center; font-size: 0.85rem; text-transform: uppercase;
      letter-spacing: 2px; color: var(--text-muted); margin-bottom: 1.5rem;
    }}
    .toc-list {{ display: flex; flex-direction: column; gap: 0.5rem; }}
    .toc-item {{
      display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1.25rem;
      background: var(--card-bg); border-radius: 12px; text-decoration: none; color: var(--text);
      box-shadow: 0 1px 3px rgba(0,0,0,0.04); transition: var(--transition); border-left: 3px solid transparent;
    }}
    .toc-item:hover {{ border-left-color: var(--primary); transform: translateX(4px); box-shadow: var(--shadow-hover); }}
    .toc-title {{ flex: 1; font-size: 0.9rem; font-weight: 500; }}
    .toc-speaker {{ font-size: 0.78rem; color: var(--text-muted); }}
    .toc-time {{ font-size: 0.75rem; color: var(--primary); font-weight: 600; white-space: nowrap; }}

    /* Session Sections */
    .session-section {{
      max-width: 800px; margin: 0 auto 2rem; padding: 0 1rem;
      opacity: 0; transform: translateY(40px);
      transition: opacity 0.6s ease-out, transform 0.6s ease-out;
    }}
    .session-section.reveal.visible {{ opacity: 1; transform: translateY(0); }}
    .session-header {{
      background: var(--card-bg); border-radius: var(--radius) var(--radius) 0 0;
      padding: 1.5rem 2rem; border-bottom: 1px solid var(--border);
    }}
    .session-header h2 {{ font-size: 1.25rem; color: var(--text); margin-bottom: 0.3rem; }}
    .session-meta {{ font-size: 0.82rem; color: var(--text-muted); }}

    .session-notes {{
      background: var(--card-bg); padding: 2rem;
      border-radius: 0 0 var(--radius) var(--radius); box-shadow: var(--shadow);
    }}
    .session-notes h1 {{
      font-size: 1.3rem; margin: 1.5rem 0 0.8rem; color: var(--text);
      padding-bottom: 0.4rem; border-bottom: 2px solid var(--primary);
    }}
    .session-notes h2 {{
      font-size: 1.1rem; margin: 1.5rem 0 0.6rem; color: var(--text);
      padding-left: 0.5rem; border-left: 4px solid var(--primary);
    }}
    .session-notes h3 {{ font-size: 0.98rem; margin: 1.2rem 0 0.5rem; color: var(--primary-dark); }}
    .session-notes p {{ margin: 0.6rem 0; font-size: 0.9rem; line-height: 1.8; color: #2d2d3a; }}
    .session-notes ul, .session-notes ol {{ padding-left: 1.5rem; margin: 0.6rem 0; }}
    .session-notes li {{ font-size: 0.9rem; margin: 0.3rem 0; line-height: 1.7; color: #2d2d3a; }}
    .session-notes strong {{ color: var(--primary-dark); font-weight: 600; }}
    .session-notes code {{
      background: #f0f0f5; padding: 2px 6px; border-radius: 4px;
      font-size: 0.84rem; color: #d63384; font-family: 'SF Mono', 'Fira Code', monospace;
    }}
    .session-notes pre {{
      background: #1a1a2e; color: #e0e0e8; padding: 1rem 1.25rem; border-radius: 10px;
      overflow-x: auto; font-size: 0.82rem; margin: 0.8rem 0;
      box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);
    }}
    .session-notes pre code {{ background: transparent; color: inherit; padding: 0; }}
    .session-notes blockquote {{
      border-left: 4px solid var(--primary); padding: 0.6rem 1rem; margin: 0.8rem 0;
      background: linear-gradient(135deg, #f0f0ff 0%, #f8f8ff 100%);
      border-radius: 0 10px 10px 0; color: #333; font-size: 0.88rem;
      box-shadow: 0 1px 4px rgba(74,74,240,0.08);
    }}
    .session-notes hr {{
      border: none; height: 1px;
      background: linear-gradient(90deg, transparent, var(--border) 20%, var(--border) 80%, transparent);
      margin: 1.5rem 0;
    }}
    .session-notes table {{
      border-collapse: collapse; width: 100%; margin: 0.8rem 0;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-radius: 8px; overflow: hidden;
    }}
    .session-notes th, .session-notes td {{
      border: 1px solid #e8e8ee; padding: 0.5rem 0.75rem; font-size: 0.85rem; color: #2d2d3a;
    }}
    .session-notes th {{ background: var(--primary); color: white; font-weight: 600; }}
    .session-notes tr:nth-child(even) td {{ background: #fafafe; }}
    .session-notes img {{ max-width: 100%; border-radius: 8px; margin: 0.5rem 0; }}

    /* Slides */
    .slides-section {{ margin-top: 1rem; }}
    .slides-toggle {{
      width: 100%; padding: 0.75rem 1.5rem; background: var(--card-bg);
      border: 1px solid var(--border); border-radius: 12px; cursor: pointer;
      font-size: 0.9rem; font-weight: 500; color: var(--primary); transition: var(--transition); text-align: center;
    }}
    .slides-toggle:hover {{ background: var(--primary-light); transform: scale(1.02); }}
    .slides-toggle.open {{ background: var(--primary); color: white; border-color: var(--primary); }}
    .slides-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 1rem; margin-top: 1rem; animation: fadeInUp 0.5s ease-out;
    }}
    .slide-card {{
      border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
      transition: var(--transition); cursor: pointer; break-inside: avoid;
    }}
    .slide-card:hover {{
      transform: translateY(-4px) scale(1.02); box-shadow: var(--shadow-hover); border-color: var(--primary);
    }}
    .slide-card img {{ width: 100%; display: block; }}
    .slide-card figcaption {{
      padding: 0.5rem 0.75rem; font-size: 0.78rem; color: var(--text-muted);
      background: #fafafa; border-top: 1px solid var(--border);
    }}

    @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(30px); }} to {{ opacity: 1; transform: translateY(0); }} }}

    /* Back to Top */
    #back-to-top {{
      position: fixed; bottom: 2rem; right: 2rem; width: 48px; height: 48px;
      border-radius: 50%; background: var(--primary); color: white; border: none;
      cursor: pointer; font-size: 1.2rem; opacity: 0; pointer-events: none;
      transition: var(--transition); box-shadow: 0 4px 15px rgba(74,74,240,0.4); z-index: 100;
    }}
    #back-to-top.visible {{ opacity: 1; pointer-events: auto; }}
    #back-to-top:hover {{ transform: scale(1.1); background: var(--primary-dark); }}

    /* Lightbox */
    #lightbox {{
      position: fixed; inset: 0; background: rgba(0,0,0,0.9); display: none;
      justify-content: center; align-items: center; z-index: 9999; cursor: zoom-out;
      animation: fadeIn 0.3s ease-out;
    }}
    #lightbox.open {{ display: flex; }}
    #lightbox img {{ max-width: 90vw; max-height: 90vh; border-radius: 8px; box-shadow: 0 20px 60px rgba(0,0,0,0.5); }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

    footer {{ text-align: center; padding: 3rem 2rem; color: var(--text-muted); font-size: 0.8rem; background: var(--card-bg); margin-top: 2rem; }}

    @media (max-width: 600px) {{
      .hero-stats {{ flex-direction: column; gap: 0.75rem; }}
      .slides-grid {{ grid-template-columns: 1fr; }}
      .session-notes {{ padding: 1rem; }}
      .toc-item {{ flex-wrap: wrap; }}
    }}
    @media print {{
      #progress-bar, #back-to-top, .hero-scroll-hint {{ display: none; }}
      .hero {{ min-height: auto; background: white; color: black; padding: 1rem; }}
      .hero h1 {{ -webkit-text-fill-color: black; background: none; }}
      .session-section {{ opacity: 1 !important; transform: none !important; max-width: 100%; }}
      .slides-grid {{ display: block; }}
      .slide-card {{ break-inside: avoid; margin-bottom: 1rem; }}
    }}
  </style>
</head>
<body>
  <div id="progress-bar"></div>

  <header class="hero">
    <div class="hero-content">
      <h1>{html.escape(conference_name)} 참석 리포트</h1>
      <p class="hero-subtitle">생성일: {generated_at}</p>
      <div class="hero-stats">
        <div class="hero-stat"><span class="hero-stat-number">{total_sessions}</span><span class="hero-stat-label">Sessions</span></div>
        <div class="hero-stat"><span class="hero-stat-number">{total_notes}</span><span class="hero-stat-label">Notes</span></div>
        <div class="hero-stat"><span class="hero-stat-number">{total_slides}</span><span class="hero-stat-label">Slides</span></div>
        <div class="hero-stat"><span class="hero-stat-number">{captioned}</span><span class="hero-stat-label">Captions</span></div>
      </div>
    </div>
    <div class="hero-scroll-hint">▼ Scroll</div>
  </header>

  <nav class="toc-container">
    <h3>목차</h3>
    <div class="toc-list">
      {toc_html}
    </div>
  </nav>

  <main>
{sections_html}
  </main>

  <footer>
    본 리포트는 Conference Notes 시스템에 의해 자동 생성되었습니다.<br>
    {generated_at}
  </footer>

  <button id="back-to-top" onclick="scrollToTop()">↑</button>

  <div id="lightbox" onclick="closeLightbox()">
    <img id="lightbox-img" src="" alt="" />
  </div>

  <script>
    // Scroll Progress
    window.addEventListener('scroll', function() {{
      var sh = document.documentElement.scrollHeight - window.innerHeight;
      var sc = (window.scrollY / sh) * 100;
      document.getElementById('progress-bar').style.width = sc + '%';
      var btn = document.getElementById('back-to-top');
      if (window.scrollY > 500) {{ btn.classList.add('visible'); }} else {{ btn.classList.remove('visible'); }}
    }});

    // Reveal on scroll
    var observer = new IntersectionObserver(function(entries) {{
      entries.forEach(function(entry) {{
        if (entry.isIntersecting) entry.target.classList.add('visible');
      }});
    }}, {{ threshold: 0.1 }});
    document.querySelectorAll('.reveal').forEach(function(el) {{ observer.observe(el); }});

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {{
      anchor.addEventListener('click', function(e) {{
        e.preventDefault();
        var t = document.querySelector(this.getAttribute('href'));
        if (t) t.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }});
    }});

    // Toggle slides
    function toggleSlides(btn) {{
      var grid = btn.nextElementSibling;
      var isOpen = grid.style.display !== 'none';
      grid.style.display = isOpen ? 'none' : 'grid';
      btn.classList.toggle('open', !isOpen);
      if (!isOpen) grid.style.animation = 'fadeInUp 0.5s ease-out';
    }}

    function scrollToTop() {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}

    // Lightbox
    document.addEventListener('click', function(e) {{
      if (e.target.closest('.slide-card img')) {{
        var img = e.target.closest('.slide-card img');
        var lb = document.getElementById('lightbox');
        document.getElementById('lightbox-img').src = img.src;
        lb.classList.add('open');
      }}
    }});
    function closeLightbox() {{ document.getElementById('lightbox').classList.remove('open'); }}

    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape') closeLightbox();
    }});
  </script>
</body>
</html>"""


# 전역 인스턴스
html_report_generator = HTMLReportGenerator()
