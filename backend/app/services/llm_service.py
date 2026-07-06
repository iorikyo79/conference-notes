"""LLM Service for Summary and Keyword Extraction (Zhipu AI GLM / Ollama)"""
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """다중 LLM 백엔드 지원 서비스 (Zhipu GLM / Ollama)

    우선순위:
    1. ZHIPU_API_KEY 설정 시 → Zhipu GLM API 사용
    2. OLLAMA_BASE_URL 접속 가능 시 → Ollama 로컬 LLM 사용
    3. 둘 다 없으면 → 규칙 기반 fallback
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-4-air",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:14b",
    ):
        """
        Args:
            api_key: Zhipu AI API 키 (환경변수 ZHIPU_API_KEY에서 자동 로드)
            model: Zhipu GLM 모델명
            ollama_url: Ollama 서버 URL
            ollama_model: Ollama 모델명
        """
        self._api_key = api_key or os.getenv("ZHIPU_API_KEY")
        self._model = model
        self._vision_model_zhipu = os.getenv("ZHIPU_VISION_MODEL", "glm-4v")
        self._vision_model_ollama = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
        self._client = None  # Zhipu client (lazy)

        self._ollama_url = ollama_url.rstrip("/")
        self._ollama_model = ollama_model
        self._ollama_available = None  # None = 미확인, True/False

        # 어떤 백엔드를 사용 중인지 추적
        self._active_backend = None  # "zhipu", "ollama", None

    def is_available(self) -> bool:
        """LLM 사용 가능 여부 (Zhipu 우선, Ollama 차선)"""
        if self._api_key is not None:
            self._active_backend = "zhipu"
            return True

        # Ollama 확인
        if self._ollama_available is None:
            self._check_ollama()

        if self._ollama_available:
            self._active_backend = "ollama"
            return True

        self._active_backend = None
        return False

    def _check_ollama(self):
        """Ollama 서버 가용성 확인"""
        try:
            import httpx
            resp = httpx.get(f"{self._ollama_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                logger.info(f"Ollama available. Models: {model_names}")
                self._ollama_available = True
            else:
                self._ollama_available = False
        except Exception:
            logger.info("Ollama not available. Install: https://ollama.ai")
            self._ollama_available = False

    def _get_client(self):
        """Zhipu AI 클라이언트 초기화 (Lazy Loading)"""
        if self._client is None:
            try:
                from zhipuai import ZhipuAI
                self._client = ZhipuAI(api_key=self._api_key)
            except ImportError:
                logger.error("zhipuai package not installed. Install: pip install zhipuai")
                raise RuntimeError("zhipuai package not installed")
        return self._client

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 3000) -> str:
        """통일된 LLM 호출 인터페이스 (백엔드 자동 선택)

        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            max_tokens: 최대 출력 토큰 수

        Returns:
            LLM 응답 텍스트
        """
        if not self.is_available():
            raise RuntimeError("No LLM backend available")

        if self._active_backend == "zhipu":
            return self._call_zhipu(system_prompt, user_prompt, max_tokens)
        elif self._active_backend == "ollama":
            return self._call_ollama(system_prompt, user_prompt, max_tokens)
        else:
            raise RuntimeError("No LLM backend available")

    def _call_zhipu(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Zhipu GLM API 호출"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content

    def _call_ollama(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Ollama 로컬 LLM 호출"""
        import httpx

        response = httpx.post(
            f"{self._ollama_url}/api/chat",
            json={
                "model": self._ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": max_tokens,
                },
            },
            timeout=300.0,  # 로컬 LLM은 응답이 느릴 수 있음
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    # === Vision (이미지 캡션) ===

    def is_vision_available(self) -> bool:
        """비전 모델 사용 가능 여부"""
        if not self.is_available():
            return False
        # Zhipu은 API 키만 있으면 비전 모델 사용 가능
        if self._active_backend == "zhipu":
            return True
        # Ollama는 비전 모델이 설치되어 있는지 확인
        if self._active_backend == "ollama":
            return self._check_ollama_vision()
        return False

    def _check_ollama_vision(self) -> bool:
        """Ollama에 비전 모델이 있는지 확인"""
        try:
            import httpx
            resp = httpx.get(f"{self._ollama_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    name = m.get("name", "").lower()
                    if "vl" in name or "vision" in name or "llava" in name:
                        return True
            return False
        except Exception:
            return False

    @staticmethod
    def _encode_image(file_path: str) -> str:
        """이미지를 base64로 인코딩"""
        import base64
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _call_vision(self, prompt: str, image_path: str, max_tokens: int = 500) -> str:
        """비전 LLM 호출 (백엔드 자동 선택)"""
        if not self.is_vision_available():
            raise RuntimeError("No vision backend available")

        if self._active_backend == "zhipu":
            return self._call_zhipu_vision(prompt, image_path, max_tokens)
        elif self._active_backend == "ollama":
            return self._call_ollama_vision(prompt, image_path, max_tokens)
        else:
            raise RuntimeError("No vision backend available")

    def _call_zhipu_vision(self, prompt: str, image_path: str, max_tokens: int) -> str:
        """Zhipu GLM-4V 비전 API 호출"""
        client = self._get_client()
        base64_img = self._encode_image(image_path)

        response = client.chat.completions.create(
            model=self._vision_model_zhipu,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                        },
                    ],
                }
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content

    def _call_ollama_vision(self, prompt: str, image_path: str, max_tokens: int) -> str:
        """Ollama 비전 모델 호출"""
        import httpx

        base64_img = self._encode_image(image_path)

        # 비전 모델이 설치되어 있으면 사용, 없으면 기본 모델에 images 필드 추가 시도
        vision_model = self._vision_model_ollama

        response = httpx.post(
            f"{self._ollama_url}/api/chat",
            json={
                "model": vision_model,
                "messages": [
                    {"role": "user", "content": prompt, "images": [base64_img]},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": max_tokens,
                },
            },
            timeout=300.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def generate_caption(
        self,
        image_path: str,
        session_title: str = "",
        speaker: str = "",
    ) -> Dict[str, Any]:
        """
        슬라이드 이미지의 AI 캡션 생성.

        Args:
            image_path: 이미지 파일 경로
            session_title: 세션 제목 (컨텍스트용)
            speaker: 연자명 (컨텍스트용)

        Returns:
            {"caption": "...", "model_used": bool, "backend": "..."}
        """
        context_parts = []
        if session_title:
            context_parts.append(f"발표 제목: {session_title}")
        if speaker:
            context_parts.append(f"연자: {speaker}")
        context = "\n".join(context_parts) if context_parts else ""

        prompt = "다음 학회 발표 슬라이드를 분석하여 간결하고 유용한 캡션을 한국어로 작성해주세요."
        prompt += "\n슬라이드의 제목, 핵심 내용, 포함된 차트/표/이미지 여부를 1-3문장으로 요약하세요."
        if context:
            prompt += f"\n\n참고 정보:\n{context}"

        if self.is_vision_available():
            try:
                caption = self._call_vision(prompt, image_path)
                return {
                    "caption": caption.strip(),
                    "model_used": True,
                    "backend": self.backend_info,
                }
            except Exception as e:
                logger.error(f"Vision caption generation failed: {e}")

        # Fallback: 비전 모델이 없으면 빈 캡션
        return {
            "caption": "",
            "model_used": False,
            "backend": "none",
        }

    @property
    def vision_backend_info(self) -> str:
        """비전 백엔드 정보"""
        if self._active_backend == "zhipu":
            return f"zhipu/{self._vision_model_zhipu}"
        elif self._active_backend == "ollama":
            return f"ollama/{self._vision_model_ollama}"
        return "none"

    @property
    def backend_info(self) -> str:
        """현재 활성 백엔드 정보"""
        if self._active_backend == "zhipu":
            return f"zhipu/{self._model}"
        elif self._active_backend == "ollama":
            return f"ollama/{self._ollama_model}"
        return "fallback"

    def organize_script(
        self,
        raw_text: str,
        session_title: str = "",
        speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        발표 스크립트(또는 필사文本)를 구조화된 마크다운 노트로 정리

        Args:
            raw_text: 정리 전 원본 텍스트 (발표 스크립트, 필사본 등)
            session_title: 세션 제목 (컨텍스트용)
            speaker: 연자명 (컨텍스트용)

        Returns:
            {"organized_content": "마크다운", "keywords": [...], "model_used": bool}
        """
        if not raw_text.strip():
            return {
                "organized_content": "",
                "keywords": [],
                "model_used": False,
            }

        if not self.is_available():
            return self._fallback_organize(raw_text, session_title)

        # 입력 길이 제한
        max_input = 12000
        text = raw_text[:max_input]

        context_parts = []
        if session_title:
            context_parts.append(f"발표 제목: {session_title}")
        if speaker:
            context_parts.append(f"연자: {speaker}")
        context = "\n".join(context_parts) if context_parts else "(컨텍스트 정보 없음)"

        title_for_output = session_title or "발표 정리"

        prompt = f"""당신은 의학 영상정보학 분야의 전문 비서입니다.
다음은 학회 발표의 스크립트(또는 필사본, 메모)입니다. 이를 읽기 좋은 구조화된 마크다운 노트로 정리해주세요.

[{context}]

[원본 텍스트]
{text}

다음 형식으로 정리해주세요:

# {title_for_output}

## 발표 개요
(2-3문장으로 이 발표의 핵심 주제와 목적을 요약)

## 핵심 내용
### [주제 1]
- 구체적인 설명이나 데이터
- 주요 포인트
### [주제 2]
- 구체적인 설명이나 데이터
- 주요 포인트
(원본 텍스트의 논리적 흐름에 따라 3-6개 소주제로 구성)

## 주요 키워드
- 키워드1
- 키워드2
(5-10개)

## 실무 적용 포인트
- (본인의 업무에 적용할 수 있는 구체적인 아이디어 2-3가지)

주의사항:
- 원본의 핵심 내용과 예시를 충실히 반영하세요
- 한국어 발표는 한국어로, 영어 발표는 영어로 정리하세요 (혼용시 적절히 배합)
- 구체적인 숫자, 모델명, 기술명은 정확히 보존하세요
- 문장은 간결하고 명확하게 작성하세요"""

        try:
            system_prompt = (
                "당신은 의학 영상정보학 분야의 전문 비서이며, "
                "발표 스크립트를 체계적이고 읽기 좋은 노트로 정리하는 데 능숙합니다. "
                "정확성을 최우선으로 하며, 핵심 정보를 누락하지 않습니다."
            )
            organized = self._call_llm(system_prompt, prompt, max_tokens=3000)
            keywords = self._extract_keywords_from_summary(organized)

            return {
                "organized_content": organized,
                "keywords": keywords,
                "model_used": True,
            }

        except Exception as e:
            logger.error(f"LLM script organization failed: {e}")
            return self._fallback_organize(raw_text, session_title)

    @staticmethod
    def _fallback_organize(raw_text: str, session_title: str) -> Dict[str, Any]:
        """LLM 없이 규칙 기반 스크립트 정리"""
        lines = raw_text.strip().split("\n")
        sections = []
        current_section = []
        for line in lines:
            if line.strip():
                current_section.append(line.strip())
            elif current_section:
                sections.append(current_section)
                current_section = []
        if current_section:
            sections.append(current_section)

        title = session_title or "발표 정리"
        result_lines = [f"# {title}\n"]
        result_lines.append("## 핵심 내용\n")

        for section in sections[:8]:
            first_line = section[0][:60]
            result_lines.append(f"### {first_line}\n")
            for line in section:
                result_lines.append(f"- {line}")
            result_lines.append("")

        # 빈도 기반 키워드
        words = raw_text.split()
        freq: Dict[str, int] = {}
        for w in words:
            w_clean = w.strip("#*-`[]{}()=*_~>,.")
            if len(w_clean) >= 2:
                freq[w_clean] = freq.get(w_clean, 0) + 1
        keywords = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:10]

        result_lines.append("\n---\n*(LLM 미사용 - 규칙 기반 정리)*")

        return {
            "organized_content": "\n".join(result_lines),
            "keywords": keywords,
            "model_used": False,
        }

    def summarize_session(
        self,
        notes_text: str,
        extracted_texts: List[str],
        session_title: str,
        speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        세션 단위 요약 + 키워드 추출

        Args:
            notes_text: 사용자가 작성한 노트 전체
            extracted_texts: 첨부파일에서 추출한 텍스트 목록
            session_title: 세션 제목
            speaker: 연자명

        Returns:
            {"summary": "...", "keywords": ["...", "..."]}
        """
        if not self.is_available():
            return self._fallback_summary(notes_text, extracted_texts, session_title)

        # 입력 텍스트 길이 제한 (너무 길면 자름)
        max_input = 8000
        combined_notes = notes_text[:max_input]
        combined_attachments = "\n---\n".join(extracted_texts)[:max_input]

        speaker_info = f"\n연자: {speaker}" if speaker else ""

        prompt = f"""당신은 의학 영상정보학 분야의 전문가입니다.
다음은 학회 발표 "{session_title}"에서 작성한 메모와 발표자료에서 추출한 텍스트입니다.{speaker_info}

[사용자 메모]
{combined_notes}

[발표자료 텍스트]
{combined_attachments if combined_attachments.strip() else "(발표자료 없음)"}

다음 형식으로 응답해주세요:

## 핵심 요약
(3-5문장으로 발표의 핵심 내용을 요약)

## 주요 키워드
- 키워드1
- 키워드2
(5-10개)

## 실무 적용 포인트
- 포인트1
- 포인트2
(2-3가지)"""

        try:
            system_prompt = "당신은 의학 영상정보학 분야의 전문가이며, 학회 참석 내용을 체계적으로 정리하는 데 능숙합니다."
            summary = self._call_llm(system_prompt, prompt, max_tokens=2000)

            # 키워드 추출 (간단한 파싱)
            keywords = self._extract_keywords_from_summary(summary)

            return {
                "summary": summary,
                "keywords": keywords,
            }

        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return self._fallback_summary(notes_text, extracted_texts, session_title)

    def generate_full_report(
        self,
        session_summaries: List[Dict[str, Any]],
        conference_name: str,
    ) -> str:
        """
        전체 학회 리포트 생성 (마크다운)

        Args:
            session_summaries: 각 세션의 요약 결과 목록
            conference_name: 학회명

        Returns:
            마크다운 형식의 전체 리포트
        """
        if not self.is_available():
            return self._fallback_full_report(session_summaries, conference_name)

        # 세션 요약들을 텍스트로 결합
        summaries_text = ""
        for i, ss in enumerate(session_summaries, 1):
            summaries_text += f"\n### 세션 {i}: {ss.get('session_title', '제목 없음')}\n"
            summaries_text += ss.get("summary", "요약 없음") + "\n"

        prompt = f"""다음은 {conference_name} 학회 참석 결과, 세션별 요약입니다.
전체 학회 참석 리포트를 마크다운 형식으로 작성해주세요.

[세션별 요약]
{summaries_text}

다음 구조로 작성:
# {conference_name} 참석 리포트

## 학회 개요
(학회 전체의 주제와 목적을 간략히 서술)

## 주요 학습 내용
(세션별 핵심 내용을 체계적으로 정리)

## 핵심 인사이트
(학회 전반에서 얻은 통찰을 3-5가지로 정리)

## 향후 적용 계획
(실무에 적용할 수 있는 구체적인 계획)"""

        try:
            system_prompt = "당신은 의학 영상정보학 분야의 전문가이며, 학회 참석 리포트를 체계적으로 작성하는 데 능숙합니다."
            return self._call_llm(system_prompt, prompt, max_tokens=3000)

        except Exception as e:
            logger.error(f"LLM full report generation failed: {e}")
            return self._fallback_full_report(session_summaries, conference_name)

    @staticmethod
    def _extract_keywords_from_summary(summary: str) -> List[str]:
        """요약 텍스트에서 키워드 섹션 파싱"""
        keywords = []
        in_keywords = False
        for line in summary.split("\n"):
            line_lower = line.lower().strip()
            if "키워드" in line:
                in_keywords = True
                continue
            if in_keywords:
                if line.startswith("##") or (line.strip() and not line.startswith("-")):
                    break
                if line.startswith("-"):
                    kw = line.lstrip("- ").strip()
                    if kw:
                        keywords.append(kw)
        return keywords[:10]

    @staticmethod
    def _fallback_summary(
        notes_text: str,
        extracted_texts: List[str],
        session_title: str,
    ) -> Dict[str, Any]:
        """LLM 없이 규칙 기반 요약"""
        # 노트의 첫 500자
        summary_preview = notes_text[:500] if notes_text else "(메모가 없습니다.)"

        # 빈도 기반 키워드 추출 (간단 버전)
        keywords = []
        if notes_text:
            words = notes_text.split()
            freq: Dict[str, int] = {}
            for w in words:
                # 마크다운 특수문자 제거
                w_clean = w.strip("#*-`[]{}()=*_~>")
                if len(w_clean) >= 2:
                    freq[w_clean] = freq.get(w_clean, 0) + 1
            keywords = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:10]

        return {
            "summary": f"## {session_title}\n\n(LLM 미사용 - 규칙 기반 요약)\n\n{summary_preview}",
            "keywords": keywords,
        }

    @staticmethod
    def _fallback_full_report(
        session_summaries: List[Dict[str, Any]],
        conference_name: str,
    ) -> str:
        """LLM 없이 규칙 기반 전체 리포트"""
        lines = [f"# {conference_name} 참석 리포트\n"]
        lines.append("## 주요 학습 내용\n")

        for ss in session_summaries:
            title = ss.get("session_title", "제목 없음")
            summary = ss.get("summary", "요약 없음")
            lines.append(f"### {title}\n")
            lines.append(f"{summary}\n")

        if not session_summaries:
            lines.append("(세션 요약이 없습니다.)\n")

        lines.append("\n---\n*(LLM 미사용 - 규칙 기반 리포트)*")
        return "\n".join(lines)


# 전역 인스턴스
llm_service = LLMService(
    model=os.getenv("ZHIPU_MODEL", "glm-4-air"),
    ollama_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
)
