# CLAUDE.md - Conference Notes 개발 가이드라인

## 프로젝트 목표

학회 참석 중 실시간으로 메모를 작성하고, 발표자료를 업로드하여 텍스트를 추출하며, 학회 종료 후 AI 기반 요약/리포트를 생성하는 웹 애플리케이션입니다.

---

## 개발 환경 설정

### 백엔드 실행

```bash
cd backend

# 의존성 설치 (최초 1회)
poetry install

# 서버 실행
poetry run uvicorn app.main:app --reload --port 8000
```

### 프론트엔드 실행

```bash
cd frontend/conference-frontend

# 의존성 설치 (최초 1회)
npm install

# 개발 서버 실행
npm run dev
```

### 환경 변수

백엔드 `.env` 파일 (선택사항):
```
ZHIPU_API_KEY=your_api_key_here
ZHIPU_MODEL=glm-4-flash
```

API 키가 없으면 규칙 기반 요약(fallback)으로 동작합니다.

### 시스템 의존성 (OCR 사용 시)

```bash
brew install tesseract tesseract-lang
```

---

## 아키텍처

### 백엔드 서비스 분리

- `storage.py`: JSON 파일 기반 데이터 CRUD
- `pdf_extractor.py`: PyMuPDF를 사용한 PDF 텍스트 추출
- `ocr_service.py`: Tesseract OCR 이미지 텍스트 추출
- `llm_service.py`: Zhipu AI GLM 기반 요약/키워드 추출 (Lazy Loading)

### API 엔드포인트

- `GET /api/health` - 헬스체크
- `GET/POST /api/conferences/` - 학회 관리
- `GET/POST/PUT/DELETE /api/notes/` - 노트 CRUD
- `POST /api/attachments/upload` - 파일 업로드 (백그라운드 텍스트 추출)
- `POST /api/reports/generate` - AI 리포트 생성

### 프론트엔드 상태 관리

- `AppContext`: 페이지 전환, 활성 학회/세션
- `NoteContext`: 노트 목록, 2초 debounce 자동저장
