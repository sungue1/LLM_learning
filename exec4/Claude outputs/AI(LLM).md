# AI(LLM) (10/12) _29일차

## 🖥️ LLM

### 용어 정리

- **AI 엔지니어**: 적은 비용으로 효과적인 결과를 내는 것
- **Gradio**: 파이썬(Python) 코드로 머신러닝 모델과 AI 웹 인터페이스를 단 몇 줄만으로 빠르게 만들어 공유할 수 있는 오픈소스 라이브러리
- **uv**: python 생태계의 다양한 관리 도구들을 하나로 통합한 패키지 및 프로젝트 관리 도구
- **uv.lock**: uv가 프로젝트의 의존성 패키지와 하위 의존성의 정확한 버전과 해시값을 고정하여 기록하는 파일
- **skill.md**: AI 에이전트의 기능을 확장하고 반복적인 워크플로우를 자동화하기 위한 모듈형 업무 매뉴얼
- **임베딩 모델(embedding model)**: 텍스트, 이미지 등의 비정형 데이터를 인공지능이 이해할 수 있는 **숫자 배열(벡터)** 로 변환하는 기계학습 모델
- **context window**: AI 모델이 한 번의 요청이나 대화에서 입력하고 출력으로 생성하는 모든 텍스트를 담아두고 참조할 수 있는 최대 범위(작업 기억)

### 환경 설정

1. python 설치
2. vscode 설치
3. vscode에 claude 연결
4. git 설치
5. vscode에 markdown 설치
6. vscode에 markdown PDF 설치
7. uv 다운로드
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   버전 확인할 때 powershell 꼭 여닫기
8. 폴더에서 `uv init --python 3.12` 명령어 실행
9. `uv venv`
10. `.venv\Scripts\activate` 명령어를 사용해 가상화 구현
    - `python --version`을 이용해서 파이썬 버전 3.12인지 확인하기
11. node 설치
    ```powershell
    winget install OpenJS.NodeJS.LTS
    ```
12. ai key들 `.env`에 저장

```plain text
OPENAI_API_KEY=
GOOGLE_API_KEY=
OLLAMA_URL=
GOOGLE_URL=

ollama pull llama3.2:3b
ollama pull qwen2.5:3b

uv add torch matplotlib
uv add pandas
```

### 실습 파일 정리

- **1_1_openai**: 응답 내에는 토큰 사용량, 모델 종류, 멈춘 이유 등 다양하게 있지만 content 즉, 답변 본문이 주요 내용
- **1_1_2_temp_maxtoken**: temperature에 따라 0이면 일관적인 대답을, 1이면 창의적인 대답을 출력 + max_tokens에 따라 모델이 생성할 수 있는 토큰 수의 상한이 정해짐. 만약 답변하기 전에 상한에 도달 시 답변 도중에 멈춤. `finish_reason`이 `length`면 잘린 것이고, `stop`이면 답변을 마친 것임
- **1_2_gemini**: openai에서 google gemini로 변경(api_key로 model 변경). 라이브러리의 경우 OpenAI의 라이브러리 유지, 모델이 바뀌어도 `"role": "system", "content"` 형태 유지
- **1_3_ollama**: ollama 모델을 사용하고 localhost 주소를 사용해서 로컬에서 모델이 작동. 로컬이어도 `"role": "system", "content"` 형태 유지
- **1_3_2_qwen**: 동일한 local 환경에서 qwen 모델 사용(base_url로 model 변경). 모델(weight와 bias)에 따라 언어 능력을 좌우, `"role": "system", "content"` 형태 유지
- **1_4_llms**: 4가지 model(openai, gemini, ollama, qwen) 동시에 비교. 이때 try/except를 사용해 한 모델이 문제가 생겨도 실행을 유지
- **1_5_tokenizer**: tiktoken 라이브러리를 사용해서 사용되는 token 개수 확인. 각 회사마다 token 계산 방법이 다르니 단순히 token 개수로 비용 비교 금지. 한국어를 사용할 경우 회사마다 다르지만 약간의 추가 token을 사용
- **1_6_stateless**: stateless = ai는 매 호출이 백지에서 시작된다. 이전 호출의 흔적이 전혀 남지 않음 → 지난 대화를 같이 넣어서 대화를 기억함. 실험이 하고 싶으면 아래 함수 사용

  ```python
  def chat_without_history(message, history):
      messages = [{"role": "system", "content": system_prompt}] + [{"role": "user", "content": message}]
  ```

- **1_6_2_stateful**: stateful = messages 리스트에 이전 대화 직접 누적하기(append 사용) or Gradio ChatInterface가 넘겨주는 history 사용하기
- **1_7_context_openai**: 이전 대화를 무한정 넣을 수 없다 = Context Window. 모델마다 context window의 값은 다르다. Context Window를 초과 시, 오래된 대화를 자름.

## 출처 및 참고 사이트

- https://wikidocs.net/238310
- https://www.geeksforgeeks.org/deep-learning/introduction-deep-learning/
- https://www.geeksforgeeks.org/deep-learning/neural-networks-a-beginners-guide/
- https://www.geeksforgeeks.org/machine-learning/getting-started-with-transformers/
- https://velog.io/@baek-seunghwan/딥러닝은-어떻게-학습할까-Gradient-Descent-vs-Adam
- https://wikidocs.net/278304
- https://wikidocs.net/book/16914
