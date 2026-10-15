# AI(RAG) (10/13) _30일차

## 🖥️ LLM

### 용어 정리

- **RAG(Retrieval-Augmented Generation)**: AI가 답변을 만들기 전에 외부 문서나 데이터베이스에서 관련 정보를 먼저 검색하고, 이를 바탕으로 정확한 답변을 생성하는 기술 → 외부에 접속하면 안 되는(폐쇄망) 산업권에 자주 쓰임

### RAG 흐름

자료 → chunk 단위로 자름 → Embedding model이 숫자 배열로 변환 → 벡터DB에 저장 → 제일 가까운 내용을 알고리즘으로 분별 → 그곳에서 내용을 가져와서 대답(LLM 사용)

> (Notion 원본에 RAG 구조 이미지가 첨부되어 있음)

### 실습 파일 정리

- `uv run .\src\0_fetch_real_data.py` → 데이터 수집하는 파일
- `uv run .\src\1_chunk.py` → 수집한 데이터를 chunk로 나누는 파일
- `uv run .\src\2_embed_and_store.py` → chunk를 embedding(벡터로 바꿈)하고 벡터DB(Chroma)에 저장하는 파일
- `uv run .\src\3_query.py --ui` → 질문과 거리가 가장 가까운 데이터 3개를 Chroma에서 뽑은 뒤, 뽑은 3개를 근거로 system 메시지에 넣고 질문은 user 메시지로 만들어 LLM에 보낸다. LLM이 생성한 한국어 답변과 검색된 근거를 웹 화면에 출력한다.

### 추가 메모

- **하드 라우팅**:
- **소프트 라우팅**:
- RAG는 채점표가 필요

## 출처 및 참고 사이트

- https://medium.com/data-science-collective/rag-architectures-a-complete-guide-for-2025-daf98a2ede8c
