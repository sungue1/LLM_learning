<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# security_rag — 프로세스 및 데이터 흐름

> CVE ID를 키로 삼아 연결된 CWE(취약점 유형) 문서를 검색하는 RAG 파이프라인
> 작성 기준: 2026-09-10 / 현재 데이터 상태 반영

---

## 1. 한눈에 보기

파이프라인은 **준비 단계(0~2)** 와 **사용 단계(3)** 로 나뉩니다.
준비 단계는 한 번만 돌리고, 사용 단계는 질문할 때마다 돕니다.

```
┌─────────────────────── 준비 단계 (한 번만) ───────────────────────┐
│                                                                    │
│  [0] 수집          [1] 청킹          [2] 임베딩·저장                │
│  0_fetch_real_     1_chunk.py       2_embed_and_store.py           │
│  data.py                                                           │
│      │                  │                    │                     │
│      ▼                  ▼                    ▼                     │
│  cwe_catalog.json   chunks.json         chroma_db/                 │
│  cve_cwe_           (298 청크)          (298 벡터)                  │
│  mapping.json                          embedding_config.json       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────── 사용 단계 (질문마다) ───────────────────────┐
│                                                                    │
│  [3] 검색·답변   3_query.py                                         │
│                                                                    │
│   질문 ─▶ CVE ID 추출 ─▶ 매핑 조회 ─▶ 벡터 검색 ─▶ LLM 답변 생성    │
│                          (필터)      (의미)      (근거 기반)        │
└────────────────────────────────────────────────────────────────────┘
```

**외부 소스는 준비 단계에서만 접근합니다.** 질문할 때는 로컬 데이터만 씁니다.

---

## 2. 전체 데이터 흐름

```
  ┌──────────────┐         ┌──────────────┐
  │  MITRE CWE   │         │   NVD API    │
  │  (XML .zip)  │         │  (CVE 정보)  │
  └──────┬───────┘         └──────┬───────┘
         │                        │
         │  download_cwe_xml()    │  fetch_cve_mappings()
         │  parse_cwe_catalog()   │  fetch_specific_cves()
         ▼                        ▼
  ┌─────────────────┐      ┌──────────────────────┐
  │ cwe_catalog.json│      │ cve_cwe_mapping.json │
  │  57개           │      │  200건               │
  │  (검색 대상)     │◀─────│  (검색 열쇠)          │
  └────────┬────────┘ filter_catalog_to_mapped()  │
           │                                      │
           │ [1] chunk_cwe_catalog()              │
           │     split_long_section()             │
           ▼                                      │
  ┌─────────────────┐                             │
  │  chunks.json    │                             │
  │  298 청크        │                             │
  │  + 메타데이터    │                             │
  └────────┬────────┘                             │
           │                                      │
           │ [2] build_embedding_function()       │
           │     collection.add()                 │
           ▼                                      │
  ┌─────────────────┐                             │
  │  chroma_db/     │                             │
  │  298 벡터        │                             │
  │  (1536차원)      │                             │
  └────────┬────────┘                             │
           │                                      │
           │              [3] 질의 시점            │
           └──────────────┬───────────────────────┘
                          ▼
                   ┌─────────────┐
                   │  3_query.py │
                   └─────────────┘
```

**핵심 설계** — CWE 문서만 임베딩하고, CVE는 **매핑 테이블로만** 연결합니다.
CVE마다 CWE 본문을 복제하면 같은 글을 수십 번 저장하게 됩니다.
현재 CVE 200건이 참조하는 CWE는 **57종**뿐입니다.

---

## 3. 단계별 상세

### [0] 수집 — `0_fetch_real_data.py`

| 항목 | 내용 |
|---|---|
| 입력 | 없음 (외부 API 호출) |
| 출력 | `cwe_catalog.json`, `cve_cwe_mapping.json`, `raw/cwec_latest.xml` |
| 소요 | 수 분 (NVD 호출 제한에 좌우) |

```
MITRE cwec_latest.xml.zip ──▶ download_cwe_xml()  ──▶ 캐시 저장
                                     │
                                     ▼
                              parse_cwe_catalog()
                                     │
                                     ▼  CWE 1,391개
NVD API ──▶ fetch_cve_mappings()  ──▶ _to_mapping()
             (KEV 200건 기본)            │  CVE 200건
                                        ▼
                          filter_catalog_to_mapped()
                                        │  --cwe-scope mapped
                                        ▼
                                   CWE 57개만 유지
```

**주요 옵션**

| 옵션 | 뜻 | 기본 |
|---|---|---|
| `--source` | `kev`(악용 확인) / `recent`(최근 공개) | `kev` |
| `--max-cves` | 수집할 CVE 최대 개수 | `200` |
| `--cve-ids` | 특정 CVE를 반드시 포함 | 없음 |
| `--cwe-scope` | `mapped`(참조된 것만) / `all`(1,391개) | `mapped` |

> NVD는 API 키가 없으면 요청 간 6초를 쉽니다.
> `.env`에 `NVD_KEY=` 또는 `NVD_API_KEY=`를 넣으면 0.7초로 줄어듭니다.

### [1] 청킹 — `1_chunk.py`

| 항목 | 내용 |
|---|---|
| 입력 | `cwe_catalog.json` (57개) |
| 출력 | `chunks.json` (298 청크) |
| 소요 | 1초 미만 (외부 호출 없음) |

```
CWE 문서 1개
  ├─ description            ─┐
  ├─ extended_description    ├─▶ chunk_cwe_catalog()
  ├─ potential_mitigations   │      │
  └─ observed_examples      ─┘      │  1,200자 초과 시
                                    ▼
                            split_long_section()
                                    │  줄 경계에서 분할
                                    ▼
                              청크 + 메타데이터
```

**섹션 단위로 나누는 이유** — CWE 문서는 MITRE가 정한 표준 구조를 따릅니다.
이미 의미 단위로 나뉘어 있는데 고정 길이(1,000자)로 자르면 그 구조가 깨집니다.

**현재 청크 분포**

| 섹션 | 청크 수 | 답하는 질문 |
|---|---|---|
| `description` | 57 | 이게 뭔가 |
| `extended_description` | 20 | 더 자세히 |
| `potential_mitigations` | 123 | **어떻게 막나** |
| `observed_examples` | 98 | 실제 사례는 |

### [2] 임베딩·저장 — `2_embed_and_store.py`

| 항목 | 내용 |
|---|---|
| 입력 | `chunks.json` |
| 출력 | `chroma_db/`, `embedding_config.json`, `tfidf_vectorizer.pkl` |
| 소요 | 수십 초 (OpenAI API 호출) |

```
chunks.json ──▶ build_embedding_function()
                        │
                        │  EMBEDDING_BACKEND 환경변수로 선택
                        ├─ openai (기본)  text-embedding-3-small, 1536차원
                        ├─ tfidf          8192차원, 키 불필요 (비교용)
                        └─ sentence-transformers
                        │
                        ▼
              client.create_collection(
                  embedding_function=...,          ← add() 시 자동 임베딩
                  metadata={"hnsw:space": "cosine"})
                        │
                        ▼
              collection.add(500개씩 배치)
                        │
                        ▼
              embedding_config.json 기록  ← 3단계가 백엔드 일치를 검사
```

> **재실행하면 컬렉션을 지우고 새로 만듭니다.** 멱등성을 위한 설계이지만,
> 그때 **컬렉션 UUID가 바뀌므로** 챗봇이 떠 있으면 옛 핸들이 무효가 됩니다.
> (`chat_fn`이 이를 감지해 자동으로 다시 열지만, 재시작이 안전합니다.)

### [3] 검색·답변 — `3_query.py`

| 항목 | 내용 |
|---|---|
| 입력 | 사용자 질문 |
| 출력 | 답변 + 근거 |
| 소요 | 1~3초 |

---

## 4. 질의 시점의 상세 흐름

```
사용자 질문
   │  "CVE-2008-2992는 어떻게 예방하나요?"
   ▼
┌──────────────────────────────────────────────┐
│ extract_cve_id()                             │
│   정규식 CVE-\d{4}-\d{4,} 로 ID를 찾는다      │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │ 못 찾음              │ 찾음
        ▼                     ▼
  usage_guide()      ┌────────────────────────────────┐
  (안내 후 종료)      │ load_cve_mapping()             │
                     │   CVE → CWE 목록 조회 (정확 일치)│
                     └───────────┬────────────────────┘
                                 │  cwe_ids = ["CWE-787"]
                                 ▼
                     ┌────────────────────────────────┐
                     │ clean_query()                  │
                     │   검색어에서 CVE ID를 제거       │
                     └───────────┬────────────────────┘
                                 │
                                 ▼
                     ┌────────────────────────────────┐
                     │ retrieve_chunks()              │
                     │   ① 메타데이터 필터             │
                     │      where cwe_id in [...]     │
                     │   ② 의미 검색 (코사인 거리)     │
                     │   → 상위 3개 청크               │
                     └───────────┬────────────────────┘
                                 │
        ┌────────────────────────┴────────┐
        │ 결과 없음                        │ 결과 있음
        ▼                                 ▼
  usage_guide()             ┌──────────────────────────┐
  (수집 안내)                │ generate_answer()        │
                            │   근거만 사용하도록 제약   │
                            │   LLM: gpt-4.1-nano      │
                            └───────────┬──────────────┘
                                        │
                                        ▼
                            ┌──────────────────────────┐
                            │ format_sources()         │
                            │   출처를 접어서 첨부       │
                            └───────────┬──────────────┘
                                        ▼
                                   답변 + 근거
```

### 이 흐름의 두 가지 핵심

**① 필터가 먼저, 의미 검색이 나중 (하이브리드 검색)**

CVE ID로 검색 범위를 먼저 좁히지 않으면 무관한 CWE 문서가 딸려 옵니다.
실측 결과입니다.

| | 상위 3개 | 거리 |
|---|---|---|
| 필터 없음 | CWE-116, CWE-94, CWE-79 (**무관**) | 0.48~0.49 |
| 필터 있음 | CWE-787 (정답) | 0.53~0.61 |

**무관한 문서의 거리가 오히려 더 낮습니다.** "예방 방법"을 묻는 질문에는
어느 CWE의 `potential_mitigations`든 잘 어울리기 때문입니다.
의미 검색만으로는 *"예방법을 설명하는 글"* 은 찾아도 *"이 CVE의 예방법"* 은 찾지 못합니다.

**② 검색어에서 CVE ID를 빼는 이유 (`clean_query`)**

| 검색어 | 상위 결과 | 거리 |
|---|---|---|
| CVE ID 포함 | `observed_examples` | **0.505** (더 낮음) |
| CVE ID 제거 | `potential_mitigations` | 0.699 |

`observed_examples` 섹션의 본문은 온통 CVE 번호 나열이라, 검색어에 번호가 있으면
'예방 방법'이라는 **의도** 대신 'CVE 번호가 많은 글'과 매칭됩니다.
거리 0.505는 의도가 맞아서가 아니라 **글자 모양이 닮아서** 나온 가짜 점수입니다.

> **거리 점수가 낮다고 좋은 검색이 아닙니다.**
> CVE ID는 이미 메타데이터 필터로 쓰이므로, 의미 검색에는 의도가 담긴 문장만 넘깁니다.

---

## 5. 파일 의존 관계

```
0_fetch_real_data.py ──▶ cwe_catalog.json ──┐
                     └─▶ cve_cwe_mapping.json ──────────────┐
                                            │               │
1_chunk.py ─────────────────────────────────┘               │
     └─▶ chunks.json ──┐                                    │
                       │                                    │
2_embed_and_store.py ──┘                                    │
     ├─▶ chroma_db/                                         │
     ├─▶ embedding_config.json ──┐                          │
     └─▶ tfidf_vectorizer.pkl    │                          │
                                 │                          │
3_query.py ──────────────────────┴──────────────────────────┘
     │  (2_embed_and_store를 import 해서 임베딩 함수를 재사용)
     └─▶ 답변
```

**3_query.py가 2_embed_and_store.py를 import 하는 이유** — 색인할 때 쓴 것과
**정확히 같은 임베딩 함수**로 질문을 벡터로 바꿔야 비교가 성립합니다.
문서는 자로 재고 질문은 저울로 잰 뒤 두 숫자를 비교하면 의미가 없는 것과 같습니다.

`embedding_config.json`은 그 일치 여부를 검사하기 위한 기록입니다.
`openai`로 색인해두고 `tfidf`로 검색하면 벡터 차원부터 다릅니다(1536 vs 8192).

---

## 6. 실행 순서

```bash
# 준비 (한 번만)
python src/0_fetch_real_data.py      # 수 분, 네트워크 필요
python src/1_chunk.py                # 1초 미만
python src/2_embed_and_store.py      # 수십 초, OpenAI API 호출

# 사용
python src/3_query.py                                    # 데모 실행
python src/3_query.py CVE-2008-2992 "how to prevent?"    # 단건 조회
python src/3_query.py --ui                               # 챗봇 (http://127.0.0.1:7860)
```

**데이터를 다시 수집했다면 1·2단계도 반드시 다시 실행하세요.**
그러지 않으면 매핑과 벡터 DB가 어긋나 검색 결과가 맞지 않습니다.

---

## 7. 현재 데이터 규모

| 항목 | 값 |
|---|---|
| CVE 매핑 | 200건 |
| CWE 문서 | 57개 (`--cwe-scope mapped`) |
| 청크 | 298개 |
| 벡터 DB | 298개 (일치) |
| 임베딩 백엔드 | `openai` / text-embedding-3-small / 1536차원 |
| 답변 생성 모델 | `gpt-4.1-nano` (`CHAT_MODEL` 환경변수로 변경) |

---

## 8. 이 프로젝트가 답할 수 있는 것과 없는 것

| 질문 | 가능? | 이유 |
|---|---|---|
| 이건 어떤 유형의 취약점인가 | O | CWE 문서에 있음 |
| 왜 위험한가 | O | CWE 문서에 있음 |
| 개발자가 어떻게 예방하나 | O | `potential_mitigations` |
| 비슷한 사례가 있나 | O | `observed_examples` |
| **SQL injection 관련 CVE가 뭐야?** | **X** | **방향이 반대** — 이 앱은 `CVE → 유형` 한 방향만 |
| 우리가 쓰는 2.14.1이 영향받나 | X | CWE 문서에 제품·버전 정보가 없음 |
| 어느 버전으로 올려야 하나 | X | 위와 같음 |

**X 항목은 [security_rag_advance](../security_rag_advance/)에서 다룹니다.**
역방향 조회, 벤더 어드바이저리, 버전 판정이 추가된 확장판입니다.

---

## 관련 문서

- [README.md](README.md) — 프로젝트 개요와 사용법
- [tfidvectorizer.md](tfidvectorizer.md) — TF-IDF 동작 원리
- [../additional_info.md](../additional_info.md) — CVE ID 체계와 데이터 구조
- 노트북 — [1_fetch](1_fetch.ipynb) · [2_chunk](2_chunk.ipynb) · [3_embed](3_embed.ipynb) · [4_query](4_query.ipynb)
