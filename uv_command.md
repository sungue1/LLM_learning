# uv 명령어 정리

> 기준: uv 0.13 / Windows PowerShell
> 전체 도움말: `uv help`, 명령별 도움말: `uv <명령> --help`

---

## 1. 프로젝트 만들기

| 명령어 | 설명 |
|---|---|
| `uv init` | 현재 폴더를 uv 프로젝트로 초기화 (`pyproject.toml` 생성) |
| `uv init 폴더명` | 새 폴더를 만들고 그 안에 프로젝트 생성 |
| `uv init --python 3.12` | Python 3.12로 프로젝트 생성 (`.python-version`에 기록) |
| `uv init --app` | 스크립트/앱용 단순 구조 (`main.py`) |
| `uv init --package` | 패키지 구조 (`src/패키지명/`) |
| `uv init --lib` | 라이브러리 구조 |
| `uv init --vcs none` | git 저장소를 만들지 않음 |

> 이미 `pyproject.toml`이 있으면 `uv init`은 에러가 납니다.
> → 버전을 바꾸려면 `uv init` 대신 `uv python pin` + `uv sync`를 사용하세요.

---

## 2. 패키지 관리

| 명령어 | 설명 |
|---|---|
| `uv add 패키지명` | 패키지 설치 + `pyproject.toml`에 추가 |
| `uv add "패키지명==1.2.3"` | 특정 버전 설치 |
| `uv add 패키지1 패키지2` | 여러 개 한 번에 설치 |
| `uv add --dev 패키지명` | 개발용 의존성으로 추가 (예: pytest, ruff) |
| `uv add -r requirements.txt` | requirements.txt의 패키지를 모두 추가 |
| `uv remove 패키지명` | 패키지 제거 + `pyproject.toml`에서 삭제 |
| `uv lock` | `uv.lock` 파일 갱신 |
| `uv lock --upgrade` | 모든 패키지를 최신 버전으로 갱신 |
| `uv lock --upgrade-package 패키지명` | 특정 패키지만 업그레이드 |
| `uv sync` | `pyproject.toml`/`uv.lock` 기준으로 `.venv`를 맞춤 (없으면 생성) |
| `uv tree` | 의존성 트리 보기 |
| `uv export -o requirements.txt` | requirements.txt로 내보내기 |

예시 (LLM 학습용):

```powershell
uv add openai anthropic python-dotenv
uv add jupyter ipykernel --dev
```

---

## 3. 실행

| 명령어 | 설명 |
|---|---|
| `uv run 파일명.py` | 프로젝트 `.venv`로 파이썬 파일 실행 (활성화 불필요) |
| `uv run python` | 프로젝트 Python으로 대화형 셸 실행 |
| `uv run python --version` | 프로젝트에서 쓰는 Python 버전 확인 |
| `uv run 명령어` | `.venv`에 설치된 도구 실행 (예: `uv run jupyter lab`) |
| `uv run --with 패키지명 파일.py` | 설치하지 않고 임시로 패키지를 추가해 실행 |

> `python --version`과 `uv run python --version`의 결과가 다르면,
> 가상환경이 활성화되지 않아 시스템 Python이 실행되고 있는 것입니다.

---

## 4. Python 버전 관리

| 명령어 | 설명 |
|---|---|
| `uv python list` | 설치 가능한/설치된 Python 목록 |
| `uv python list --only-installed` | 설치된 Python만 보기 |
| `uv python install 3.12` | Python 3.12 설치 |
| `uv python uninstall 3.12` | Python 3.12 제거 |
| `uv python pin 3.12` | 이 프로젝트의 Python 버전을 3.12로 고정 (`.python-version` 수정) |
| `uv python find` | 현재 사용될 Python 경로 확인 |

**프로젝트 Python 버전 바꾸기**

```powershell
uv python pin 3.12
uv sync
uv run python --version
```

> `pyproject.toml`의 `requires-python` 범위와 맞아야 합니다.
> (예: `requires-python = ">=3.13"`이면 3.12로 pin할 수 없음)

---

## 5. 가상환경

| 명령어 | 설명 |
|---|---|
| `uv venv` | `.venv` 생성 |
| `uv venv --python 3.12` | 특정 버전으로 `.venv` 생성 |
| `.venv\Scripts\activate` | 가상환경 활성화 (PowerShell) |
| `deactivate` | 가상환경 비활성화 |

**PowerShell에서 `activate` 실행 오류가 날 때** (실행 정책 문제):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser   # 처음 한 번만
```

> 활성화하지 않고 항상 `uv run ...`으로 실행해도 됩니다.

---

## 6. pip 호환 명령 (`uv pip`)

`pyproject.toml`에 기록하지 않고 pip처럼 쓰고 싶을 때 사용합니다.

| 명령어 | 설명 |
|---|---|
| `uv pip install 패키지명` | 현재 가상환경에 설치 |
| `uv pip install -r requirements.txt` | requirements.txt로 설치 |
| `uv pip uninstall 패키지명` | 제거 |
| `uv pip list` | 설치된 패키지 목록 |
| `uv pip show 패키지명` | 패키지 정보 |
| `uv pip freeze` | requirements 형식으로 출력 |

> 프로젝트에서는 `uv add`/`uv remove` 사용을 권장합니다.
> (`uv pip`으로 설치한 것은 `uv sync` 시 사라질 수 있음)

---

## 7. 전역 도구 (`uv tool`)

프로젝트와 상관없이 어디서나 쓰는 CLI 도구를 설치합니다.

| 명령어 | 설명 |
|---|---|
| `uv tool install ruff` | 도구 전역 설치 |
| `uv tool list` | 설치된 도구 목록 |
| `uv tool upgrade ruff` | 도구 업그레이드 |
| `uv tool uninstall ruff` | 도구 제거 |
| `uvx ruff check` | 설치 없이 일회성 실행 (`uv tool run`과 동일) |

---

## 8. 관리 / 기타

| 명령어 | 설명 |
|---|---|
| `uv --version` | uv 버전 확인 |
| `uv self update` | uv 업데이트 (독립 설치본인 경우) |
| `uv cache clean` | 캐시 삭제 |
| `uv cache dir` | 캐시 위치 확인 |

---

## 자주 쓰는 흐름

**새 프로젝트 시작**

```powershell
uv init --python 3.12
uv add 패키지명
uv run main.py
```

**다른 사람 프로젝트(또는 다른 PC)에서 환경 복원**

```powershell
uv sync
uv run 파일명.py
```

**Jupyter 노트북에서 이 환경 쓰기**

```powershell
uv add --dev ipykernel
```

VS Code에서 노트북 오른쪽 위 커널 선택 → `.venv` 선택

---

## 주요 파일

| 파일 | 역할 |
|---|---|
| `pyproject.toml` | 프로젝트 정보, 의존성 목록, `requires-python` |
| `uv.lock` | 정확히 설치된 버전 기록 (직접 수정 X) |
| `.python-version` | 이 프로젝트에서 쓸 Python 버전 |
| `.venv/` | 가상환경 폴더 (지워도 `uv sync`로 다시 만들 수 있음) |
