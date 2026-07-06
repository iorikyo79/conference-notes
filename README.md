# Conference Notes

학회 참석 중 실시간 메모 작성, 발표자료 업로드, AI 기반 요약/리포트 생성 웹 애플리케이션

## 주요 기능

- **실시간 메모 작성**: 세션별 마크다운 에디터, 2초 debounce 자동저장
- **세션 삭제**: 불필요한 세션(쉬는 시간, 점심 등) 개별 삭제
- **빈 노트 정리**: 내용이 없는 노트 일괄 삭제
- **EXIF 기반 슬라이드 자동 분류**: 이미지 업로드 시 촬영 시간(EXIF)으로 발표 세션 자동 매칭 (±5분 tolerance)
- **AI 슬라이드 캡션**: GLM-4V / Ollama 비전 모델로 슬라이드 이미지 캡션 생성
- **HTML 통합 리포트**: 노트 + 슬라이드 이미지 + 캡션을 통합한 자체완결형 HTML 생성 (AI 개입 없음)
- **AI 요약 리포트**: Zhipu GLM / Ollama 기반 세션별 요약 및 전체 학회 리포트

## 기술 스택

### Backend
- **FastAPI** + Uvicorn
- **JSON 파일 기반 저장소** (MVP 단계, DB 없음)
- **Pillow**: EXIF 메타데이터 추출
- **PyMuPDF**: PDF 텍스트 추출
- **Tesseract OCR**: 이미지 텍스트 추출
- **Zhipu AI GLM** / **Ollama**: LLM 요약, 비전 캡션

### Frontend
- **React 19** + TypeScript
- **Vite**
- **react-markdown** + remark-gfm

## 시작하기

### 백엔드 실행

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

### 프론트엔드 실행

```bash
cd frontend/conference-frontend
npm install
npm run dev
```

### 환경 변수 (선택)

`backend/.env`:
```
ZHIPU_API_KEY=your_api_key_here
ZHIPU_MODEL=glm-4-air
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

API 키가 없으면 규칙 기반 fallback으로 동작합니다.

### 시스템 의존성 (OCR 사용 시)

```bash
brew install tesseract tesseract-lang
```

## 아키텍처

```
conference-notes/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI 엔드포인트
│   │   │   ├── attachments.py   # 파일 업로드, EXIF 분류, 캡션
│   │   │   ├── conferences.py   # 학회/세션 CRUD
│   │   │   ├── notes.py         # 노트 CRUD, 스크립트 정리
│   │   │   └── reports.py       # 리포트 생성 (AI/HTML)
│   │   ├── services/
│   │   │   ├── exif_service.py       # EXIF DateTimeOriginal 추출
│   │   │   ├── session_matcher.py    # EXIF 시간 → 세션 매칭
│   │   │   ├── llm_service.py        # LLM 요약/캡션 (Zhipu/Ollama)
│   │   │   ├── html_report_generator.py  # HTML 리포트 생성
│   │   │   ├── ocr_service.py        # Tesseract OCR
│   │   │   └── pdf_extractor.py      # PyMuPDF PDF 추출
│   │   ├── models/schemas.py    # Pydantic 모델
│   │   └── config/settings.py   # 설정
│   ├── storage/
│   │   ├── data/                # JSON 데이터 (git 제외)
│   │   └── uploads/             # 업로드 파일 (git 제외)
│   └── pyproject.toml
├── frontend/
│   └── conference-frontend/
│       └── src/
│           ├── components/      # NoteEditor, SessionSelector
│           ├── contexts/        # AppContext, NoteContext
│           ├── pages/           # Home, SessionView, Attachments, Report
│           ├── services/api.ts  # API 클라이언트
│           └── types/api.ts     # TypeScript 타입
└── CLAUDE.md                   # 개발 가이드라인
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/health` | 헬스체크 |
| GET/POST | `/api/conferences/` | 학회 목록 조회/생성 |
| GET/POST/PUT/DELETE | `/api/notes/` | 노트 CRUD |
| DELETE | `/api/notes/empty/bulk` | 빈 노트 일괄 삭제 |
| POST | `/api/notes/organize-and-save` | 스크립트 정리 + 저장 |
| POST | `/api/attachments/upload` | 단일 파일 업로드 (EXIF 자동 분류) |
| POST | `/api/attachments/upload-batch` | 다중 파일 배치 업로드 |
| POST | `/api/attachments/{id}/caption` | 개별 캡션 생성 |
| POST | `/api/attachments/sessions/{id}/captions` | 세션 일괄 캡션 생성 |
| PATCH | `/api/attachments/{id}/session` | 세션 재할당 |
| POST | `/api/reports/generate` | 리포트 생성 (AI 요약 / HTML 통합) |
| GET | `/api/reports/{id}/export` | 리포트 내보내기 (MD / HTML) |
| DELETE | `/api/conferences/{id}/sessions/{id}` | 세션 삭제 |

## 라이선스

MIT
