# Ollama 명령어 정리

> 기준: Ollama CLI / Windows PowerShell
> 전체 도움말: `ollama help`, 명령별 도움말: `ollama <명령> --help`
> 모델 목록: https://ollama.com/library

---

## 1. 설치 / 확인

| 명령어 | 설명 |
|---|---|
| `winget install Ollama.Ollama` | Ollama 설치 (또는 https://ollama.com/download 에서 설치 파일 다운로드) |
| `ollama --version` | 설치 버전 확인 |
| `ollama help` | 전체 명령어 목록 |

> Windows에서는 설치 후 Ollama가 **백그라운드 앱(트레이 아이콘)** 으로 자동 실행됩니다.
> 설치 직후 `ollama`를 찾을 수 없다고 나오면 터미널(VS Code 포함)을 껐다 켜세요. (PATH 갱신)

---

## 2. 모델 받기 / 관리

| 명령어 | 설명 |
|---|---|
| `ollama pull 모델명` | 모델 다운로드 (예: `ollama pull llama3.2`) |
| `ollama pull 모델명:태그` | 특정 크기/버전 다운로드 (예: `ollama pull qwen2.5:7b`) |
| `ollama list` | 내 PC에 받은 모델 목록 (`ollama ls`와 동일) |
| `ollama show 모델명` | 모델 정보 (파라미터 수, 컨텍스트 길이, 양자화 등) |
| `ollama show 모델명 --modelfile` | 모델의 Modelfile 보기 |
| `ollama cp 원본 새이름` | 모델 복사 (이름 바꾸기용) |
| `ollama rm 모델명` | 모델 삭제 (디스크 공간 확보) |

**모델 이름 규칙**: `모델명:태그`

| 예시 | 의미 |
|---|---|
| `llama3.2` | 태그 생략 = `llama3.2:latest` (기본 크기) |
| `qwen2.5:7b` | 70억 파라미터 버전 |
| `gemma3:4b` | 40억 파라미터 버전 |
| `nomic-embed-text` | 임베딩 전용 모델 (RAG용) |

> 대략적인 메모리 기준: 3~4B ≈ 4GB, 7~8B ≈ 8GB, 13~14B ≈ 16GB (RAM 또는 GPU VRAM)
> 처음에는 작은 모델(3B~8B)부터 시작하세요.

---

## 3. 실행 / 대화

| 명령어 | 설명 |
|---|---|
| `ollama run 모델명` | 대화형 채팅 시작 (모델이 없으면 자동으로 pull) |
| `ollama run 모델명 "질문"` | 한 번만 질문하고 답변 출력 후 종료 |
| `ollama run 모델명 --verbose` | 답변 후 속도(tokens/s) 등 통계 표시 |
| `ollama ps` | 현재 메모리에 올라가 있는 모델 (CPU/GPU 사용 여부 확인) |
| `ollama stop 모델명` | 메모리에서 모델 내리기 |

```powershell
ollama run llama3.2 "파이썬 리스트 컴프리헨션을 예시와 함께 설명해줘"
Get-Content 파일.txt | ollama run llama3.2 "이 내용을 3줄로 요약해줘"
```

**대화 중 사용하는 명령 (`>>>` 프롬프트에서)**

| 명령 | 설명 |
|---|---|
| `/bye` | 대화 종료 (또는 `Ctrl + D`) |
| `/clear` | 대화 기록 초기화 |
| `/show info` | 현재 모델 정보 |
| `/set system "지시문"` | 시스템 프롬프트 설정 |
| `/set parameter temperature 0.2` | 파라미터 변경 |
| `/save 이름` | 현재 설정/대화를 새 모델로 저장 |
| `/load 모델명` | 다른 모델로 전환 |
| `"""` | 여러 줄 입력 시작/끝 |
| `/?` | 도움말 |

> `ollama ps`의 PROCESSOR 열이 `100% GPU`이면 GPU를 쓰는 중, `CPU`가 섞여 있으면 VRAM이 부족해 느려진 상태입니다.

---

## 4. 서버 (API)

Ollama는 `http://localhost:11434`에서 API 서버로 동작합니다. 파이썬 코드는 이 서버에 요청을 보냅니다.

| 명령어 | 설명 |
|---|---|
| `ollama serve` | 서버 직접 실행 (트레이 앱이 이미 실행 중이면 불필요) |
| `curl http://localhost:11434` | 서버 동작 확인 (`Ollama is running` 출력) |
| `curl http://localhost:11434/api/tags` | 설치된 모델 목록 (JSON) |

| API 경로 | 용도 |
|---|---|
| `/api/generate` | 단일 프롬프트 → 답변 |
| `/api/chat` | 메시지 목록(대화) → 답변 |
| `/api/embed` | 텍스트 → 임베딩 벡터 |
| `/api/tags` | 모델 목록 |
| `/v1/...` | **OpenAI 호환 API** (`openai` 패키지로 그대로 사용 가능) |

> `ollama serve` 실행 시 `address already in use` 에러 → 이미 트레이 앱이 서버를 띄운 상태입니다. 그대로 쓰면 됩니다.

---

## 5. 파이썬에서 사용 (uv 프로젝트)

**방법 1: `ollama` 공식 패키지**

```powershell
uv add ollama
```

```python
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "안녕? 자기소개 해줘"}],
)
print(response["message"]["content"])
```

**방법 2: OpenAI 호환 API (`openai` 패키지)**

```powershell
uv add openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")  # api_key는 아무 값이나 OK

response = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "안녕? 자기소개 해줘"}],
)
print(response.choices[0].message.content)
```

> 방법 2는 `base_url`만 바꾸면 OpenAI 코드와 같은 형태라, 로컬 모델 ↔ 클라우드 모델 전환 연습에 좋습니다.
> 실행: `uv run 파일명.py` (Ollama 앱/서버가 켜져 있어야 함)

---

## 6. 나만의 모델 만들기 (Modelfile)

`Modelfile`이라는 파일을 만들고 `ollama create`로 등록합니다.

```dockerfile
FROM llama3.2

PARAMETER temperature 0.3
PARAMETER num_ctx 8192

SYSTEM """
당신은 파이썬 초보자를 돕는 친절한 튜터입니다. 항상 한국어로, 예시 코드와 함께 답하세요.
"""
```

| 명령어 | 설명 |
|---|---|
| `ollama create 이름 -f Modelfile` | Modelfile로 새 모델 생성 |
| `ollama run 이름` | 만든 모델 실행 |
| `ollama show 이름 --modelfile` | 설정 확인 |

| Modelfile 지시어 | 설명 |
|---|---|
| `FROM` | 기반 모델 (필수) |
| `SYSTEM` | 시스템 프롬프트 |
| `PARAMETER` | `temperature`, `num_ctx`(컨텍스트 길이), `top_p`, `stop` 등 |
| `TEMPLATE` | 프롬프트 템플릿 (보통 건드리지 않음) |

---

## 7. 환경 변수 (Windows)

| 변수 | 설명 |
|---|---|
| `OLLAMA_MODELS` | 모델 저장 위치 (기본: `C:\Users\사용자\.ollama\models`) |
| `OLLAMA_HOST` | 서버 주소/포트 (기본: `127.0.0.1:11434`) |
| `OLLAMA_KEEP_ALIVE` | 모델을 메모리에 유지하는 시간 (기본 `5m`) |
| `OLLAMA_CONTEXT_LENGTH` | 기본 컨텍스트 길이 |

**모델 저장 위치를 D드라이브로 옮기기** (C드라이브 용량이 부족할 때)

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama\models", "User")
```

> 설정 후 **트레이 아이콘에서 Ollama를 완전히 종료(Quit)하고 다시 실행**해야 적용됩니다.
> 기존 모델은 새 위치로 옮기거나 다시 pull 하세요.

---

## 자주 쓰는 흐름

**처음 시작**

```powershell
ollama --version
ollama pull llama3.2
ollama run llama3.2
```

**파이썬 프로젝트에서 쓰기**

```powershell
ollama list            # 사용할 모델 이름 확인
uv add ollama          # 또는 uv add openai
uv run main.py
```

**느리거나 안 될 때 점검**

```powershell
curl http://localhost:11434   # 서버가 켜져 있는지
ollama ps                     # GPU를 쓰고 있는지, 어떤 모델이 올라가 있는지
ollama stop 모델명             # 메모리 정리
```

---

## 주요 위치 / 파일

| 이름 | 의미 |
|---|---|
| `C:\Users\사용자\.ollama\models` | 다운로드한 모델 파일 (용량 큼) |
| `%LOCALAPPDATA%\Ollama` | 로그 파일 (`server.log`) — 오류 확인용 |
| `Modelfile` | 사용자 정의 모델 설정 파일 |
| `localhost:11434` | Ollama API 서버 기본 주소 |
