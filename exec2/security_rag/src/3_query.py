
"""
3단계: 검색 (Retrieval)

'취약점 유형 학습/교육용 RAG' 시나리오:
  사용자가 CVE ID를 입력하면
  1) cve_cwe_mapping.json에서 해당 CVE에 연결된 CWE ID를 찾고
  2) 벡터 DB에서 그 CWE ID로 필터링한 뒤, 질문과 가까운
     섹션(정의/완화 방법/사례 등)을 검색해 온다.

CVE ID로 먼저 좁히고 그 안에서만 의미 검색을 하는 구조라, 엉뚱한 CWE 문서가
딸려 오지 않는다. 벡터 검색만으로는 얻기 어려운 정확도를 메타데이터 필터가
보완하는 전형적인 hybrid 패턴이다.

한계: CWE 문서에는 "이 CVE가 이 제품의 어느 코드에서 어떻게 터졌는지"가 없다.
여기서 얻는 답은 "이 CVE가 속한 취약점 유형은 무엇이고 왜 위험하며 어떻게
막는가"까지다. 제품별 영향도·패치 버전은 NVD/벤더 어드바이저리를 따로 봐야 한다.

사용 예:
    python src/3_query.py                                  # 데이터에서 예시를 골라 데모
    python src/3_query.py CVE-2021-44228
    python src/3_query.py CVE-2021-44228 "how do I prevent this?"
    python src/3_query.py --ui                             # gradio 챗봇 UI 실행

--ui로 실행하면 웹 브라우저에서 대화하듯 물어볼 수 있는 챗봇이 뜬다.
이때는 검색(Retrieval)에서 끝나지 않고, 찾은 근거를 LLM에게 넘겨 답변까지
생성한다. 즉 RAG의 R과 G가 모두 갖춰진 형태가 된다.
"""
import json
import os
import pickle  # noqa: F401  (2_embed_and_store가 vectorizer를 pickle로 저장한다)
import re
import sys
from collections import Counter
from importlib import import_module
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).parent))
embed_module = import_module("2_embed_and_store")

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
COLLECTION_NAME = "cwe_catalog"

DEFAULT_QUESTION = "why is this dangerous and how do I prevent it?"
DEFAULT_TOP_K = 3


# 챗봇 답변을 생성할 LLM. 환경변수 CHAT_MODEL로 바꿀 수 있다.
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1-nano")

# 사용자가 아무 데나 적어 넣은 CVE ID를 찾아내기 위한 정규식.
#   CVE-  연도 4자리  -  일련번호 4자리 이상
# 실제 CVE 번호는 뒤가 4자리보다 길어질 수 있어서 {4,}로 열어 둔다.
# re.IGNORECASE를 함께 쓰므로 'cve-2021-44228'처럼 소문자로 적어도 잡힌다.
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)

# LLM에게 주는 지시문. {context} 자리에 검색해 온 CWE 문서 조각이 들어간다.
#
# 이 프롬프트에서 가장 중요한 문장은 "주어진 근거만 사용하라"는 부분이다.
# LLM은 아는 척하며 그럴듯한 거짓말(환각, hallucination)을 만들어내는데,
# 보안 정보에서 그런 일이 벌어지면 위험하다. 근거를 제한하고, 근거에 없으면
# 없다고 말하라고 못박아 두는 것이 RAG에서 답변 품질을 지키는 핵심이다.
SYSTEM_PROMPT_TEMPLATE = """당신은 소프트웨어 보안 취약점을 가르치는 교육용 도우미입니다.

아래 <근거>는 이 CVE에 연결된 MITRE CWE(취약점 유형) 공식 문서에서 검색해 온
내용입니다. 이 문서는 해당 CVE가 어떤 유형의 취약점인지를 설명하므로,
"왜 위험한가", "어떻게 예방하는가", "비슷한 사례가 있는가" 같은 질문에는
이 근거를 바탕으로 충실하게 답하세요.

답변 규칙:
- 근거에 담긴 내용을 우선 사용하고, 초급 개발자가 이해할 수 있게 한국어로
  쉽게 풀어 설명하세요. 영어 원문을 그대로 옮기지 말고 뜻을 풀어 쓰세요.
- 근거에 예방·완화 방법이 있으면 항목별로 정리해 구체적으로 알려주세요.
- 근거에 전혀 없는 내용을 지어내지 마세요.
- 다만 특정 제품의 영향 버전이나 패치 방법처럼 CWE 문서가 담고 있지 않은 것을
  물으면, 그것은 CWE 문서의 범위 밖이라고 알리고 NVD나 벤더 공지를 확인하라고
  안내하세요.

<대상 CVE>
{cve_info}

<근거>
{context}
"""


def load_cve_mapping() -> dict:
    """CVE 매핑 파일을 읽어, CVE ID로 바로 찾을 수 있는 딕셔너리로 바꾼다.

    무슨 일을 하나:
      data/cve_cwe_mapping.json에는 CVE 정보가 '리스트'로 저장돼 있다.

          [ {"cve_id": "CVE-2021-44228", "cwe_ids": [...], ...},
            {"cve_id": "CVE-2014-0160",  "cwe_ids": [...], ...}, ... ]

      그런데 우리가 하려는 일은 "CVE-2021-44228의 정보를 다오"이다. 리스트인
      채로 찾으려면 매번 처음부터 훑으며 cve_id를 비교해야 한다. 그래서
      CVE ID를 열쇠로 삼는 딕셔너리로 바꿔둔다.

          { "CVE-2021-44228": {...전체 정보...},
            "CVE-2014-0160":  {...전체 정보...} }

      이러면 mapping["CVE-2021-44228"] 한 번으로 즉시 찾을 수 있다. 항목이
      200개든 20만 개든 걸리는 시간이 거의 같다. 이렇게 '찾기 좋은 형태로
      미리 바꿔두는' 것을 인덱싱이라고 하며, 실무에서 아주 자주 쓰는 기법이다.

    딕셔너리 컴프리헨션:
      return {m["cve_id"]: m for m in mapping_list}
      리스트를 돌면서 '열쇠: 값' 쌍을 만들어 딕셔너리를 짓는 문법이다.
      for 문으로 풀어 쓰면 이것과 같다.

          result = {}
          for m in mapping_list:
              result[m["cve_id"]] = m
          return result

      값으로 m 자체를 넣었으므로, 원래 리스트에 있던 정보(product, cvss_score
      등)가 그대로 다 들어 있다. 열쇠만 새로 붙인 셈이다.
    """
    with open(DATA_DIR / "cve_cwe_mapping.json", encoding="utf-8") as f:
        mapping_list = json.load(f)
    return {m["cve_id"]: m for m in mapping_list}


def get_collection():
    """저장해둔 벡터 DB를 열어, 검색할 수 있는 컬렉션 객체를 돌려준다.

    무슨 일을 하나:
      2_embed_and_store.py가 만들어 놓은 data/chroma_db/를 열고, 검색에 쓸
      임베딩 함수를 붙여서 돌려준다. 이 객체에 .query()를 부르면 검색이 된다.

    왜 임베딩 함수를 또 넘겨야 하나 (핵심 개념):
      벡터 DB에 저장된 것은 숫자 벡터뿐이다. 우리가 검색할 때 던지는 것은
      "how do I prevent this?" 같은 글이므로, 이 글도 똑같은 방식으로 벡터로
      바꿔야 저장된 벡터들과 비교할 수 있다.

      중요한 건 '똑같은 방식'이어야 한다는 점이다. 문서는 자로 재고 질문은
      저울로 잰 다음 두 숫자를 비교하면 아무 의미가 없는 것과 같다. 그래서
      색인할 때 쓴 것과 정확히 같은 임베딩 함수를 여기서 다시 만들어 넘긴다.
      TF-IDF의 경우 저장해둔 vectorizer 파일을 불러오는 것이 바로 이 때문이다.

    백엔드 불일치를 막는 검사:
      OpenAI로 색인해두고 TF-IDF로 검색하려 하면, 벡터의 칸 수부터 달라
      (1536 대 8192) 검색이 실패하거나 엉뚱한 결과가 나온다. 게다가 이 에러는
      메시지가 불친절해서 원인을 찾기 어렵다.

      그래서 2단계가 남겨둔 embedding_config.json을 읽어, 지금 쓰려는 방식과
      다르면 무엇이 어긋났고 어떻게 고치면 되는지 한국어로 알려주며 멈춘다.
      config_path.exists()로 파일이 있을 때만 검사하는 것은, 예전에 만든
      DB라 그 파일이 없어도 그냥 진행할 수 있게 하기 위해서다.

      raise SystemExit(메시지)는 프로그램을 정상적으로 끝내면서 메시지를
      보여준다. 일반 예외처럼 긴 오류 추적(traceback)을 쏟아내지 않아서,
      사용자의 설정 실수를 알릴 때 쓰기 좋다.

    get_collection과 create_collection의 차이:
      create_collection은 새로 만드는 것이라, 이미 있으면 에러가 난다.
      get_collection은 이미 있는 것을 여는 것이라, 없으면 에러가 난다.
      여기서 없다는 에러가 나면 2_embed_and_store.py를 아직 안 돌린 것이다.
    """
    # 색인 때 쓴 것과 같은 임베딩 함수여야 질의 벡터가 같은 공간에 놓인다.
    # 다르면 차원이 안 맞거나(에러), 맞더라도 의미 없는 결과가 나온다.
    embedding_fn = embed_module.build_embedding_function()
    config_path = embed_module.CONFIG_PATH
    if config_path.exists():
        indexed_backend = json.loads(config_path.read_text(encoding="utf-8"))["backend"]
        if indexed_backend != embedding_fn.name():
            raise SystemExit(
                f"색인은 '{indexed_backend}' 백엔드로 만들어졌는데 지금은 "
                f"'{embedding_fn.name()}'로 검색하려 합니다.\n"
                f"EMBEDDING_BACKEND={indexed_backend} 로 맞추거나, "
                f"원하는 백엔드로 2_embed_and_store.py를 다시 실행하세요."
            )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME, embedding_function=embedding_fn)


def clean_query(question: str) -> str:
    """검색어에서 CVE ID를 빼낸다. 검색 품질에 생각보다 큰 영향을 준다.

    무엇이 문제였나 (실제로 겪은 사례):
      "CVE-2021-44228은 개발자가 어떻게 예방하나요?"를 그대로 검색어로 쓰면,
      기대와 달리 완화 방법(potential_mitigations)이 아니라 사례 목록
      (observed_examples) 청크가 최상위로 올라왔다.

      이유는 이렇다. observed_examples 섹션의 본문은 이런 모양이다.

          CVE-2020-9054: Chain: improper input validation ...
          CVE-2020-3452: Chain: security product has improper ...
          CVE-2020-3161: Improper input validation of HTTP requests ...

      온통 CVE 번호로 채워져 있다. 그래서 검색어에 'CVE-2021-44228'이 들어가면
      임베딩이 '이 글은 CVE 번호를 잔뜩 나열한 글과 닮았다'고 판단해 버린다.
      정작 사용자가 알고 싶은 '어떻게 예방하나요'라는 의도는 묻혀버린다.

      실제 측정 결과:
          검색어에 CVE ID 포함 -> observed_examples 3개 (거리 0.495~0.514)
          검색어에서 CVE 제거   -> potential_mitigations 3개 (거리 0.686~0.711)

      거리 숫자만 보면 오히려 나빠진 것 같지만 착각이다. 앞의 0.495는 질문의
      '의도'가 아니라 'CVE 번호라는 글자 모양'이 닮아서 나온 가짜 점수다.
      거리 값은 항상 '무엇과 닮았는지'와 함께 봐야 한다.

    왜 CVE ID를 빼도 괜찮은가:
      CVE ID는 이미 다른 방식으로 쓰이고 있다. retrieve_chunks()가 그 ID로
      매핑 테이블을 조회해 where 필터로 검색 범위를 좁힌다. 즉 CVE ID는
      '어느 문서를 볼지' 정하는 데 쓰이고, 남은 문장은 '그 문서 안에서 무엇을
      볼지' 정하는 데 쓰인다. 역할이 나뉘어 있으므로 검색어에서는 빼는 게 맞다.

      이는 하이브리드 검색에서 흔히 챙기는 부분이다. 필터로 쓸 정보는 필터에만
      쓰고, 의미 검색에는 의도가 담긴 문장만 넘긴다.

    sub()가 하는 일:
      CVE_PATTERN.sub(" ", question)은 정규식과 일치하는 부분을 공백으로
      바꾼다. 그 뒤 split()과 join()으로 남은 공백을 정리해 한 줄로 만든다.

    빈 문자열이 되는 경우:
      사용자가 "CVE-2021-44228"만 딱 입력하면 다 지워져 검색어가 비어버린다.
      빈 검색어를 넘기면 의미 없는 결과가 나오므로, 그때는 기본 질문
      ("왜 위험하고 어떻게 예방하나")으로 대신한다. 사용자가 CVE ID만
      던졌을 때 가장 알고 싶어 할 내용이기 때문이다.
    """
    stripped = " ".join(CVE_PATTERN.sub(" ", question).split())
    return stripped or DEFAULT_QUESTION


def retrieve_chunks(cve_id: str, question: str, top_k: int = DEFAULT_TOP_K,
                    collection=None) -> list[dict]:
    """CVE에 연결된 CWE 문서 중 질문과 가까운 조각을 찾아 목록으로 돌려준다.

    이 함수의 역할:
      RAG에서 '검색(Retrieval)'만 담당하는 순수한 함수다. 화면에 출력하지 않고
      결과를 값으로 돌려주기만 한다.

      원래 이 로직은 answer_for_cve() 안에 검색과 출력이 섞여 들어 있었는데,
      gradio 챗봇도 똑같은 검색이 필요해지면서 검색 부분만 따로 떼어냈다.
      이렇게 하면 명령줄 출력과 웹 UI가 완전히 같은 검색 코드를 쓰게 되어,
      한쪽만 고쳐서 두 결과가 달라지는 일이 생기지 않는다.

      '계산하는 함수'와 '보여주는 함수'를 분리하는 것은 자주 쓰이는 설계 원칙이다.
      계산 함수는 화면에 의존하지 않으므로 테스트하기도 쉽다.

    두 단계 검색 (자세한 설명은 answer_for_cve 참고):
      1) cve_cwe_mapping.json에서 이 CVE에 연결된 CWE 번호를 찾고
      2) 그 CWE의 문서 조각만 대상으로 질문과 가까운 것을 고른다

    반환값:
      찾은 조각들의 딕셔너리 리스트. 가까운 순서대로 정렬돼 있다.
        [{"cwe_id": "CWE-502", "cwe_name": "Deserialization of Untrusted Data",
          "section": "potential_mitigations", "distance": 0.518,
          "text": "헤더를 뺀 본문", "header": "[CWE-502 ... ]"}, ...]

      찾지 못했거나 이 CVE가 데이터에 없으면 빈 리스트 []를 돌려준다.
      호출부는 결과가 비었는지만 확인하면 되므로 다루기 쉽다.

    예외를 던지지 않는 이유:
      '데이터에 없는 CVE'는 프로그램의 버그가 아니라 사용자가 흔히 하는 입력이다.
      챗봇에서 그때마다 예외가 나면 대화가 끊기므로, 빈 결과로 조용히 돌려주고
      안내 문구는 호출부가 상황에 맞게(터미널이냐 채팅이냐) 만들도록 맡긴다.
    """
    mapping = load_cve_mapping()
    if cve_id not in mapping:
        return []

    cwe_ids = mapping[cve_id]["cwe_ids"]
    collection = collection or get_collection()
    results = collection.query(
        query_texts=[clean_query(question)],
        n_results=top_k,
        # 이 CVE에 연결된 CWE 문서로만 검색 범위를 제한한다.
        where={"cwe_id": {"$in": cwe_ids}},
    )

    chunks = []
    for doc, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        # 1_chunk.py가 본문 맨 앞에 붙여둔 '[CWE-89 ... - Description]' 헤더를
        # 본문과 분리해 둔다. 화면에는 따로 표시하고, LLM에게는 함께 넘긴다.
        header, _, body = doc.partition("\n")
        chunks.append({
            "cwe_id": meta["cwe_id"],
            "cwe_name": meta["cwe_name"],
            "section": meta["section"],
            "distance": distance,
            "header": header,
            "text": body.strip(),
        })
    return chunks


def answer_for_cve(cve_id: str, question: str, top_k: int = DEFAULT_TOP_K,
                   collection=None) -> None:
    """CVE ID와 질문을 받아, 관련 CWE 문서 조각을 찾아 화면에 보여준다. 이 프로젝트의 핵심.

    두 단계로 검색한다 (이 구조가 이 프로젝트에서 가장 배울 만한 부분):

      1단계 - 매핑 테이블로 범위 좁히기 (정확한 일치)
              cve_cwe_mapping.json에서 이 CVE에 연결된 CWE 번호를 찾는다.
              CVE-2021-44228이면 CWE-20, 400, 502, 917이 나온다.
              이건 추측이 아니라 NVD 분석가가 확정한 사실이므로 100% 정확하다.

      2단계 - 그 범위 안에서만 의미 검색 (유사도)
              위에서 찾은 CWE의 문서 조각만 대상으로, 질문과 뜻이 가까운 것을
              고른다. "어떻게 예방하나요"라고 물으면 완화 방법 섹션이,
              "실제 사례가 있나요"라고 물으면 사례 섹션이 걸린다.

      왜 이렇게 하나:
        벡터 검색만 쓰면 질문과 단어가 비슷하다는 이유로 이 CVE와 아무 상관없는
        CWE 문서가 딸려 온다. 반대로 매핑만 쓰면 그 CWE의 모든 섹션이 통째로
        나와서 정작 궁금한 부분을 못 찾는다. 둘을 겹쳐 쓰면 '확실히 관련 있는
        문서 중에서, 질문에 가장 맞는 부분'만 남는다.

        이렇게 정확한 조건 필터와 의미 검색을 함께 쓰는 방식을 하이브리드 검색이라
        부르며, 실무 RAG에서 품질을 끌어올리는 가장 효과적인 방법 중 하나다.

    파라미터:
      cve_id     -- 조회할 CVE. 매핑 파일에 있는 것만 가능하다.
      question   -- 알고 싶은 것. 문서가 영문이라 영어로 물어야 잘 걸린다.
      top_k      -- 가져올 문서 조각의 개수(기본 3). 너무 늘리면 관련 없는
                    내용까지 딸려 오고, 너무 줄이면 답에 필요한 근거가 빠진다.
      collection -- 이미 열어둔 벡터 DB가 있으면 넘긴다. 없으면 직접 연다.
                    여러 CVE를 연달아 조회할 때 DB를 매번 다시 여는 것은
                    낭비이고, 특히 TF-IDF는 그때마다 pickle을 다시 읽는다.
                    한 번 열어 재사용하라고 만든 통로다.

      collection = collection or get_collection()
      파이썬의 or는 앞의 값이 None이면 뒤의 값을 택한다. "넘겨준 게 있으면
      그걸 쓰고, 없으면 새로 연다"를 한 줄로 쓴 관용적인 표현이다.

    where 조건 (1단계를 실제로 수행하는 부분):
      where={"cwe_id": {"$in": cwe_ids}}
      "메타데이터의 cwe_id가 이 목록 안에 있는 청크만 대상으로 삼아라"는 뜻이다.
      $in은 '이 중 하나와 같으면'을 뜻하는 조건 기호로, MongoDB 같은 DB에서
      쓰는 표기법을 Chroma도 그대로 따랐다.

      이 필터가 동작하는 이유는 1_chunk.py에서 청크마다 cwe_id를 메타데이터로
      넣어뒀기 때문이다. 앞 단계에서 심어둔 정보가 여기서 결실을 맺는 셈이다.

    결과를 [0]으로 꺼내는 이유:
      documents = results["documents"][0]
      Chroma의 query()는 질문을 여러 개 한꺼번에 받을 수 있게 설계돼 있어서,
      결과도 '질문마다 하나씩' 담긴 리스트로 온다. 우리는 질문을 하나만
      넣었으므로 첫 번째([0])가 그 답이다. 이 [0]을 빠뜨려 리스트 안의
      리스트를 그대로 출력하는 실수가 흔하다.

    zip으로 세 목록을 함께 도는 부분:
      Chroma는 본문, 메타데이터, 거리를 각각 별도의 리스트로 준다.

          documents  = ["본문1", "본문2", "본문3"]
          metadatas  = [{...}, {...}, {...}]
          distances  = [0.518, 0.526, 0.543]

      같은 순번끼리가 한 짝이므로, zip()으로 세 리스트를 나란히 묶어 한 번에
      꺼내 쓴다. 인덱스 변수를 만들어 documents[i], metadatas[i]처럼 쓰는 것보다
      읽기 쉽고 실수가 적다.

    거리(distance) 값 읽는 법:
      0에 가까울수록 질문과 비슷하고, 1에 가까우면 거의 무관하다는 뜻이다.
      대략 0.5 안팎이면 잘 맞은 것이고, 0.9를 넘으면 사실상 못 찾은 것이다.
      TF-IDF로 돌리면 이 값이 대부분 0.9 이상 나오는데, 그것이 곧 단어 일치
      방식의 한계를 보여주는 증거다. 검색 결과를 그냥 믿지 말고 이 숫자를
      함께 보는 습관을 들이면 RAG의 품질을 스스로 판단할 수 있다.

      {distance:.3f}는 소수점 셋째 자리까지만 출력하라는 서식이다.

    본문에서 첫 줄을 떼는 부분:
      body = doc.split("\\n", 1)[-1]
      1_chunk.py가 본문 맨 앞에 '[CWE-89 ... - Description]' 헤더를 붙여뒀는데,
      화면에는 그 정보를 이미 따로 출력하고 있어 중복이다. split("\\n", 1)은
      첫 줄바꿈에서 딱 한 번만 잘라 [헤더, 나머지 전부]를 만들고, [-1]로
      뒤쪽만 가져온다. 인자 1을 안 주면 모든 줄바꿈에서 잘려 본문이 조각난다.

    반환값이 없는 이유 (-> None):
      이 함수는 결과를 돌려주지 않고 화면에 직접 출력한다. 교육용으로 흐름을
      바로 보여주기에는 편하지만, 실제 서비스에서는 결과를 return으로 돌려주고
      화면에 그리는 일은 별도 코드가 맡는 편이 낫다. 그래야 같은 검색 기능을
      웹 API나 LLM 답변 생성에도 재사용할 수 있기 때문이다.

    RAG의 나머지 절반:
      이름의 R(Retrieval, 검색)까지가 여기서 하는 일이다. 실제 RAG 서비스는
      여기서 찾은 청크들을 LLM에게 "이 근거만 보고 답하라"고 함께 넘겨
      G(Generation, 생성)까지 간다. 이 프로젝트는 검색이 제대로 되는지를
      눈으로 확인하는 데 집중하려고 일부러 그 앞에서 멈춘다. 검색이 엉망이면
      LLM을 붙여도 결국 엉뚱한 답이 나오므로, 순서상으로도 이쪽이 먼저다.
    """
    mapping = load_cve_mapping()
    if cve_id not in mapping:
        print(f"\n'{cve_id}'에 대한 CWE 매핑 정보가 없습니다.")
        print("data/cve_cwe_mapping.json에 있는 CVE만 조회할 수 있습니다. "
              "다른 CVE를 쓰려면 0_fetch_real_data.py의 수집 조건을 바꾸세요.")
        return

    entry = mapping[cve_id]
    cwe_ids = entry["cwe_ids"]
    score = entry.get("cvss_score")
    score_label = f"{score} ({entry.get('severity', '')})".strip() if score else "N/A"

    print(f"\n[CVE 조회] {cve_id}")
    print(f"  제품: {entry.get('product', '(unknown)')}")
    print(f"  CVSS: {score_label}   공개일: {entry.get('published', '')[:10]}")
    print(f"  연결된 CWE: {', '.join(cwe_ids)}")

    # 실제 검색은 retrieve_chunks()가 한다. 이 함수는 그 결과를 보기 좋게
    # 출력하는 일만 맡는다.
    chunks = retrieve_chunks(cve_id, question, top_k=top_k, collection=collection)
    if not chunks:
        print("  -> 해당 CWE의 문서 청크를 찾지 못했습니다.")
        return

    print(f"\n[질문] {question}")
    print("[검색된 근거 청크]")
    for chunk in chunks:
        print(f"\n  - {chunk['cwe_id']} / {chunk['section']}  (거리 {chunk['distance']:.3f})")
        print(f"    {chunk['cwe_name']}")
        print(f"    {chunk['text'][:300]}...")


def pick_demo_cves(limit: int = 3) -> list[str]:
    """인자 없이 실행했을 때 보여줄 예시 CVE를 데이터에서 알아서 고른다.

    왜 이런 함수가 필요한가:
      예시 CVE ID를 코드에 그냥 적어두면, 0_fetch_real_data.py의 수집 조건을
      바꾸는 순간 그 CVE가 데이터에 없어서 "매핑 정보가 없습니다"만 나온다.
      실제로 이 프로젝트도 처음에는 가짜 ID가 박혀 있어 그런 문제가 있었다.
      그래서 지금 있는 데이터에서 골라 쓰도록 만들었다. 코드가 데이터에 맞춰
      스스로 적응하는 셈이다.

    고르는 기준:
      자주 등장하는 CWE에 연결된 CVE를 우선한다. 많이 쓰이는 CWE일수록 MITRE
      문서가 충실히 채워져 있어서 검색 결과가 볼 만하게 나오기 때문이다.
      드문 CWE는 설명이 한 줄뿐인 경우가 있어 시연용으로 적합하지 않다.

    Counter가 하는 일:
      frequency = Counter(cwe for m in mapping.values() for cwe in m["cwe_ids"])
      Counter는 목록에 각 값이 몇 번 나오는지 세어주는 표준 도구다. 모든 CVE의
      CWE 번호를 쏟아부으면 이런 결과가 나온다.

          Counter({'CWE-79': 23, 'CWE-416': 18, 'CWE-89': 12, ...})

      직접 딕셔너리를 만들어 세려면 '처음 보는 열쇠인지' 확인하는 코드가
      필요한데, Counter는 그걸 알아서 해준다.

    sorted와 key의 정렬 규칙:
      key=lambda m: (-max(frequency[c] for c in m["cwe_ids"]), m["cve_id"])

      lambda는 이름 없는 짧은 함수를 그 자리에서 만드는 문법이다. sorted는
      각 항목을 이 함수에 넣어 나온 값을 기준으로 순서를 정한다.

      돌려주는 값이 튜플이라 두 기준으로 정렬된다.
        첫째 -- 그 CVE가 가진 CWE 중 가장 자주 등장하는 것의 빈도. 앞에 붙은
                마이너스가 핵심인데, 파이썬 정렬은 항상 작은 것부터이므로
                부호를 뒤집어 '빈도가 큰 것이 앞으로' 오게 만드는 요령이다.
        둘째 -- 빈도가 같을 때는 CVE ID 알파벳 순. 이 기준이 없으면 실행할
                때마다 순서가 달라져 결과를 재현하기 어려워진다. 늘 같은
                결과가 나오게 만드는 것은 디버깅에 큰 도움이 된다.

    used_cwes로 중복을 피하는 이유:
      가장 흔한 CWE부터 고르다 보면, 예시 세 개가 전부 같은 CWE에 걸려 똑같은
      문서만 세 번 보여주게 된다. 이미 쓴 CWE는 건너뛰어 서로 다른 취약점
      유형이 나오게 하면 시연 효과가 훨씬 좋다.

    반환값:
      CVE ID 문자열 리스트. 예: ['CVE-2010-0806', 'CVE-2009-4324', ...]
      데이터에 CVE가 limit개보다 적으면 있는 만큼만 돌려준다.
    """
    mapping = load_cve_mapping()
    frequency = Counter(cwe for m in mapping.values() for cwe in m["cwe_ids"])

    picked, used_cwes = [], set()
    ranked = sorted(
        mapping.values(),
        key=lambda m: (-max(frequency[c] for c in m["cwe_ids"]), m["cve_id"]),
    )
    for entry in ranked:
        primary = entry["cwe_ids"][0]
        if primary in used_cwes:
            continue
        used_cwes.add(primary)
        picked.append(entry["cve_id"])
        if len(picked) >= limit:
            break
    return picked


# --------------------------------------------------------------------------
# gradio 챗봇 UI
#
# 여기부터는 웹 브라우저에서 대화하듯 쓸 수 있는 화면을 만드는 부분이다.
# 위쪽 CLI가 '검색 결과를 그대로 보여주는' 도구라면, 이쪽은 검색한 근거를
# LLM에게 넘겨 사람이 읽을 답변까지 만들어 주는 진짜 RAG 챗봇이다.
#
#     사용자 질문
#       -> CVE ID 찾아내기        (extract_cve_id)
#       -> 관련 CWE 문서 검색      (retrieve_chunks)   ... RAG의 R
#       -> LLM이 근거로 답 생성    (generate_answer)   ... RAG의 G
#       -> 답변 + 출처를 화면에    (chat_fn)
# --------------------------------------------------------------------------

def extract_cve_id(message: str) -> str | None:
    """사용자가 쓴 문장 어디에 섞여 있든 CVE ID를 찾아낸다.

    왜 필요한가:
      명령줄에서는 CVE ID를 첫 번째 인자로 정확히 받았지만, 챗봇에서는
      사람이 자연스럽게 문장으로 쓴다.

          "CVE-2021-44228이 왜 위험한가요?"
          "cve-2014-0160 알려줘"
          "Log4Shell(CVE-2021-44228) 예방 방법은?"

      이 문장들에서 CVE ID만 골라내야 매핑 테이블을 조회할 수 있다.

    정규식(regular expression)이란:
      '이런 모양의 글자'를 찾는 규칙을 적는 문법이다. 파일 위쪽에 정의한
      CVE_PATTERN이 그 규칙이다.

          CVE-\\d{4}-\\d{4,}
          │    │      └ 숫자가 4개 이상 (일련번호는 5자리, 6자리도 있다)
          │    └ 숫자 정확히 4개 (연도)
          └ 이 글자 그대로

      search()는 문장 전체를 훑어 처음 일치하는 부분을 찾는다. match()라는
      비슷한 함수도 있는데 그건 문장 '맨 앞'부터 일치해야 해서, 문장 중간에
      섞인 CVE ID는 못 찾는다. 여기서 search를 쓰는 이유다.

    .upper()를 하는 이유:
      매핑 테이블의 열쇠는 'CVE-2021-44228'처럼 전부 대문자다. 사용자가
      소문자로 적었다면 그대로는 딕셔너리에서 못 찾으므로 대문자로 맞춰준다.
      정규식에 re.IGNORECASE를 준 덕분에 찾는 것 자체는 되지만, 찾은 뒤
      형태를 통일하는 일은 따로 해줘야 한다.

    반환값:
      찾으면 'CVE-2021-44228' 같은 문자열, 없으면 None.
      호출부는 None인지 보고 "CVE ID를 알려달라"고 안내한다.
    """
    found = CVE_PATTERN.search(message)
    return found.group().upper() if found else None


def format_cve_info(cve_id: str) -> str:
    """LLM과 사용자에게 보여줄 CVE 요약 한 줄을 만든다.

    매핑 파일에 들어 있는 제품, CVSS 점수, 심각도, 공개일을 한 줄로 정리한다.
    이 정보를 프롬프트에 함께 넣어주면 LLM이 "이 취약점은 CVSS 10.0으로
    매우 심각합니다"처럼 맥락을 살린 답을 할 수 있다.

    주의:
      product는 이 CVE가 영향을 주는 수많은 제품 중 첫 번째 하나일 뿐이다
      (0_fetch_real_data.py의 _extract_product 설명 참고). 그래서 프롬프트에
      '대표 제품 예시'라고 못박아, LLM이 이것을 유일한 영향 대상인 것처럼
      단정해 말하지 않도록 한다.
    """
    entry = load_cve_mapping().get(cve_id)
    if entry is None:
        return f"{cve_id} (매핑 정보 없음)"

    score = entry.get("cvss_score")
    severity = entry.get("severity", "")
    score_label = f"{score} ({severity})".strip() if score else "점수 없음"
    return (
        f"{cve_id} / CVSS {score_label} / 공개일 {entry.get('published', '')[:10]}\n"
        f"연결된 CWE: {', '.join(entry['cwe_ids'])}\n"
        f"대표 제품 예시(전체 목록 아님): {entry.get('product', '(unknown)')}"
    )


def generate_answer(cve_id: str, question: str, chunks: list[dict]) -> str:
    """검색해 온 근거를 LLM에게 넘겨 사람이 읽을 답변을 만든다. RAG의 'G' 부분.

    무슨 일을 하나:
      retrieve_chunks()가 찾아온 CWE 문서 조각들을 하나의 글로 이어붙여
      '근거'로 만들고, 그 근거만 보고 답하라는 지시와 함께 LLM에게 보낸다.

    왜 LLM에게 근거를 넣어주나 (RAG의 존재 이유):
      LLM에게 그냥 "CVE-2021-44228이 뭔가요"라고 물으면, 학습 시점 이후의
      정보는 모르고 아는 내용도 부정확하게 섞어 말할 수 있다. 대신 신뢰할 수
      있는 문서를 찾아 함께 넣어주면, LLM은 그 문서를 '읽고' 정리하는 역할만
      하게 된다. 이것이 검색 증강 생성(Retrieval-Augmented Generation)이다.

      그래서 RAG의 품질은 대부분 검색 단계에서 결정된다. 엉뚱한 문서를 찾아
      넣으면 아무리 좋은 LLM도 엉뚱한 답을 한다.

    메시지의 두 가지 역할:
      messages 리스트에 두 개를 담아 보낸다.
        role="system" -- LLM에게 주는 배경 지시. 역할, 규칙, 근거가 들어간다.
                         사용자에게는 보이지 않는다.
        role="user"   -- 사용자가 실제로 던진 질문.
      이렇게 지시와 질문을 나눠 담으면 LLM이 둘을 혼동하지 않는다.

    temperature=0인 이유:
      LLM이 답을 고를 때의 '무작위성'을 조절하는 값이다. 0이면 가장 확률이
      높은 답만 고르므로 같은 질문에 거의 같은 답이 나온다. 창작이라면 높은
      값이 좋지만, 문서 내용을 정확히 전달해야 하는 여기서는 0이 맞다.

    API 키가 없으면:
      OpenAI 키가 없어도 챗봇을 쓸 수 있도록, 예외를 잡아서 안내 문구를
      돌려준다. 그러면 답변 생성만 빠지고 검색된 근거는 그대로 볼 수 있다.
      기능 하나가 없다고 전체가 멈추지 않게 만드는 것을 우아한 성능 저하
      (graceful degradation)라고 한다.
    """
    if not chunks:
        return "관련 문서를 찾지 못해 답변을 생성할 수 없습니다."

    # 근거 조각들을 하나의 글로 합친다. 헤더를 살려 넣어야 LLM이 각 조각이
    # 어느 CWE의 어느 섹션인지 알고 답에 반영할 수 있다.
    context = "\n\n".join(f"{c['header']}\n{c['text']}" for c in chunks)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        cve_info=format_cve_info(cve_id), context=context
    )

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content
    except Exception as error:
        # 키가 없거나, 네트워크가 끊겼거나, 모델 이름이 틀렸을 수 있다.
        return (
            f"답변 생성을 건너뜁니다 ({type(error).__name__}: {error}).\n"
            f"아래 '검색된 근거'는 정상적으로 찾았으니 그대로 확인하세요.\n"
            f"OPENAI_API_KEY를 .env에 설정하면 답변까지 생성됩니다."
        )


def format_sources(chunks: list[dict]) -> str:
    """검색된 근거를 채팅 화면에 접어서 보여줄 마크다운으로 만든다.

    왜 출처를 보여주나:
      LLM의 답만 보여주면 사용자는 그 말이 맞는지 확인할 방법이 없다.
      어느 문서의 어느 부분에서 나온 답인지 함께 보여주면 직접 검증할 수 있고,
      거리 값을 보고 '이번 검색은 잘 됐는지'까지 판단할 수 있다.
      실무 RAG에서 출처 표시는 선택이 아니라 필수에 가깝다.

    <details> 태그:
      마크다운 안에서도 쓸 수 있는 HTML 태그로, 접었다 펼 수 있는 영역을
      만든다. 근거 전문은 길어서 항상 펼쳐두면 정작 답변이 묻히므로,
      기본은 접어두고 사용자가 원할 때만 펴보게 한다.
    """
    lines = ["\n\n<details><summary>검색된 근거 보기</summary>\n"]
    for chunk in chunks:
        lines.append(
            f"\n**{chunk['cwe_id']} · {chunk['section']}** "
            f"(거리 {chunk['distance']:.3f}) — {chunk['cwe_name']}\n\n"
            f"> {chunk['text'][:500]}...\n"
        )
    lines.append("\n</details>")
    return "".join(lines)


def usage_guide(headline: str, explain_key: bool = True) -> str:
    """답할 수 없을 때, 왜 그런지와 무엇을 하면 되는지 알려주는 안내문을 만든다.

    왜 이렇게 길게 쓰나:
      챗봇이 "CVE ID를 적어주세요" 한 줄만 돌려주면, 사용자는 세 가지를 구별할
      수 없다.
        (1) 데이터에 없어서 못 답하는 것인지
        (2) 이 앱이 원래 못 하는 질문인지
        (3) 내가 질문을 잘못 쓴 것인지
      실제로 "SQL injection 관련 CVE가 뭐야?"라고 물으면 이 앱은 거절하는데,
      CWE-89 문서와 그 유형의 CVE는 데이터에 멀쩡히 들어 있다. 답할 수 있는
      것을 못 답하는 것이 아니라 **방향이 반대**라서 못 하는 것인데, 한 줄짜리
      안내로는 그 사실이 전혀 전달되지 않는다.

      그래서 (a) 왜 거절하는지, (b) 그럼 뭘 물어야 하는지, (c) 이 앱으로 안 되는
      질문은 어디로 가야 하는지를 함께 알려준다. 막다른 길에 안내판을 세우는 셈이다.

    explain_key를 나누는 이유:
      'CVE ID가 아예 없는 경우'와 '적었지만 데이터에 없는 경우'는 이어서 알려줄
      내용이 대부분 같지만, 후자에게 "왜 CVE ID가 필요한가요?"를 설명하면
      엉뚱하다. 그 사람은 이미 ID를 적었기 때문이다. 그 부분만 빼고 보여준다.
    """
    examples = pick_demo_cves(3)
    first = examples[0]
    second = examples[1] if len(examples) > 1 else first
    third = examples[2] if len(examples) > 2 else first

    why_key = (
        "### 왜 CVE ID가 필요한가요?\n\n"
        "이 앱이 검색하는 문서는 MITRE **CWE**(취약점 *유형*) 문서입니다.\n"
        "CVE ID는 그중 **어느 유형 문서를 볼지 좁혀주는 열쇠**입니다.\n"
        "열쇠가 없으면 무관한 유형 문서까지 딸려 와서 답을 믿을 수 없게 됩니다.\n\n"
    ) if explain_key else ""

    return (
        f"{headline}\n\n"
        f"{why_key}"
        "### 이렇게 물어보세요\n\n"
        f"- `{first}는 어떤 종류의 취약점인가요?`\n"
        f"- `{second}를 개발자가 예방하려면 어떻게 해야 하나요?`\n"
        f"- `{third}과 비슷한 실제 사고 사례가 있나요?`\n\n"
        f"지금 데이터에 들어 있는 CVE 예시: {', '.join(examples)}\n\n"
        "### 이 앱이 답할 수 없는 질문\n\n"
        "| 질문 | 왜 못 하나 | 어디로 가야 하나 |\n"
        "|---|---|---|\n"
        "| \"SQL injection 관련 CVE가 뭐야?\" | **방향이 반대입니다.** 이 앱은 "
        "`CVE → 유형` 한 방향만 지원합니다 | `security_rag_advance` 프로젝트 "
        "(유형 → CVE 역방향 조회 지원) 또는 "
        "[NVD 검색](https://nvd.nist.gov/vuln/search) |\n"
        "| \"우리가 쓰는 2.14.1이 영향받나요?\" | CWE 문서에는 **제품·버전 정보가 "
        "없습니다** | `security_rag_advance` (OSV 버전 범위로 판정) |\n"
        "| \"패치는 어느 버전으로 올려야 하나요?\" | 위와 같습니다 | 벤더 공지 / "
        "[NVD](https://nvd.nist.gov/vuln/search) |\n\n"
        "### 원하는 CVE가 데이터에 없다면\n\n"
        "```bash\n"
        "python src/0_fetch_real_data.py --cve-ids CVE-2021-44228\n"
        "python src/1_chunk.py\n"
        "python src/2_embed_and_store.py\n"
        "```\n"
        "수집을 다시 했다면 **이 챗봇도 다시 시작**하세요."
    )


def chat_fn(message: str, history) -> str:
    """gradio 챗봇이 메시지를 받을 때마다 부르는 함수. 대화 한 번을 처리한다.

    gradio와의 약속:
      gr.ChatInterface는 사용자가 메시지를 보낼 때마다 이 함수를 부르고,
      돌려준 문자열을 챗봇 말풍선으로 보여준다. 인자 두 개를 받기로 정해져 있다.
        message -- 사용자가 방금 입력한 글
        history -- 지금까지의 대화 기록

      여기서는 history를 쓰지 않는다. 질문마다 CVE ID를 새로 찾아 검색하는
      구조라 이전 대화를 참고할 필요가 없기 때문이다. 다만 gradio가 인자
      두 개로 부르기 때문에 받기는 해야 한다. 이런 매개변수를 그냥 두는 것은
      약속된 형태를 맞추기 위한 흔한 처리다.

      (직전 질문의 CVE를 기억하게 만들고 싶다면 history를 뒤져 마지막 CVE ID를
       찾아 쓰면 된다. 연습 과제로 삼기 좋은 부분이다.)

    처리 흐름과 각 단계의 실패 대응:
      1. 메시지에서 CVE ID 찾기
         못 찾으면 -> 예시를 들어 CVE ID를 적어달라고 안내
      2. 그 CVE가 데이터에 있는지 확인 (검색 결과가 비었는지로 판단)
         없으면 -> 수집된 CVE 목록에 없다고 알리고, 쓸 수 있는 예시를 보여줌
      3. 근거로 답변 생성
      4. 답변 + 접어놓은 출처를 함께 반환

      각 단계마다 막혔을 때 '무엇이 문제고 다음에 뭘 하면 되는지'를 알려주는
      것이 중요하다. 챗봇이 그냥 "오류"라고만 하면 사용자는 할 수 있는 게 없다.

    컬렉션을 전역에 캐시하는 이유:
      벡터 DB를 여는 일은 메시지마다 반복하기에는 무겁다. 특히 TF-IDF는 그때마다
      pickle 파일을 다시 읽는다. 그래서 처음 한 번만 열고 모듈 전역 변수에
      담아두었다가 이후에는 재사용한다. 이렇게 '한 번 계산한 결과를 보관해두고
      다시 쓰는' 방식을 캐싱(caching)이라고 한다.

      global 선언은 함수 안에서 바깥 변수의 값을 바꾸겠다는 뜻이다. 이게 없으면
      파이썬은 같은 이름의 새 지역 변수를 만들어버려서, 캐시가 저장되지 않고
      매번 다시 열리게 된다.
    """
    global _collection_cache

    if _collection_cache is None:
        _collection_cache = get_collection()

    cve_id = extract_cve_id(message)

    # 이 프로젝트는 'CVE ID를 열쇠로 삼는다'는 한 가지 개념만 다룬다.
    # CVE ID가 없으면 검색을 시작하지 않고, 무엇을 어떻게 물어야 하는지 안내한다.
    # (유형만으로 찾기·역방향 조회는 security_rag_advance에서 다룬다.)
    if cve_id is None:
        return usage_guide("**질문에서 CVE ID를 찾지 못했습니다.**")

    # 챗봇이 떠 있는 동안 2_embed_and_store.py를 실행하면, 그 스크립트가 컬렉션을
    # 지우고 새로 만들면서 컬렉션 UUID가 바뀐다. 캐시에 들어 있던 옛 핸들은
    # 그때부터 "Collection [...] does not exist" 로 실패한다.
    # 화면에는 이유 없이 'Error'만 뜨므로, 여기서 한 번 다시 열어보고 재시도한다.
    try:
        chunks = retrieve_chunks(cve_id, message, collection=_collection_cache)
    except Exception:
        _collection_cache = get_collection()
        chunks = retrieve_chunks(cve_id, message, collection=_collection_cache)

    if not chunks:
        return usage_guide(
            f"**`{cve_id}`는 수집된 데이터에 없습니다.**\n\n"
            f"이 챗봇은 `data/cve_cwe_mapping.json`에 있는 CVE만 답할 수 있습니다. "
            f"(NVD가 CWE를 붙이지 않은 CVE는 수집 단계에서 제외되므로, "
            f"`--cve-ids {cve_id}`로 지정해도 들어오지 않을 수 있습니다.)",
            explain_key=False,
        )

    answer = generate_answer(cve_id, message, chunks)
    return f"{answer}{format_sources(chunks)}"


# chat_fn이 벡터 DB를 매번 다시 열지 않도록 담아두는 자리. 처음 질문이 올 때
# 한 번 채워지고 그 뒤로는 재사용된다.
_collection_cache = None


def launch_ui(share: bool = False) -> None:
    """gradio 챗봇 화면을 만들어 웹 브라우저에 띄운다.

    실행 방법:
        python src/3_query.py --ui

      실행하면 터미널에 http://127.0.0.1:7860 같은 주소가 뜬다. 브라우저로
      그 주소를 열면 대화할 수 있다. 종료는 터미널에서 Ctrl+C.

    gr.ChatInterface가 해주는 일:
      챗봇 화면에 필요한 것(입력창, 전송 버튼, 말풍선 목록, 대화 기록 관리,
      재시도/되돌리기 버튼)을 알아서 다 만들어 준다. 우리는 '메시지를 받아
      답을 돌려주는 함수' 하나만 넘기면 된다. 웹 개발을 몰라도 화면을 만들 수
      있어서 AI 데모에 널리 쓰인다.

    주요 인자:
      fn       -- 메시지가 올 때마다 부를 함수. 여기서는 chat_fn.
      examples -- 화면에 미리 띄워줄 예시 질문. 처음 열었을 때 뭘 물어야 할지
                  모르는 사용자를 위해, 실제 데이터에 있는 CVE로 만들어 넣는다.
                  코드에 고정해두지 않고 pick_demo_cves()로 그때그때 뽑기
                  때문에 데이터가 바뀌어도 항상 동작하는 예시가 표시된다.

    import를 함수 안에서 하는 이유:
      gradio는 무거워서 불러오는 데 시간이 걸린다. 파일 맨 위에 두면 명령줄로
      간단히 검색만 할 때도 매번 그 시간을 기다려야 하고, gradio를 설치하지
      않은 사람은 CLI조차 쓸 수 없게 된다. UI를 켤 때만 부르면 그런 부담이 없다.

    share 인자:
      True로 주면 gradio가 임시 공개 주소를 만들어 외부에서도 접속할 수 있게
      한다. 남에게 데모를 보여줄 때 편하지만 인터넷에 공개되는 것이므로,
      기본값은 False로 두고 필요할 때만 켜는 것이 안전하다.

    실행 전 확인:
      벡터 DB가 없으면(2_embed_and_store.py를 아직 안 돌렸으면) 첫 질문에서야
      에러가 나서 원인을 알기 어렵다. 그래서 화면을 띄우기 전에 미리 한 번
      열어보고, 문제가 있으면 그 자리에서 알려준다.
    """
    global _collection_cache

    import gradio as gr

    # 화면을 띄우기 전에 벡터 DB와 임베딩 백엔드가 정상인지 미리 확인한다.
    _collection_cache = get_collection()
    print(f"벡터 DB 준비 완료: {_collection_cache.count()}개 청크")
    print(f"답변 생성 모델: {CHAT_MODEL}")

    demo_cves = pick_demo_cves(3)
    gr.ChatInterface(
        fn=chat_fn,
        title="CVE 취약점 학습 도우미",
        description=(
            "**CVE ID를 함께 적어** 질문하면 MITRE CWE 공식 문서를 검색해 답합니다. "
            "답변 아래 '검색된 근거 보기'를 펼치면 어떤 문서에서 나온 답인지 확인할 수 있습니다.\n\n"
            "이 앱은 `CVE → 취약점 유형` **한 방향**만 답합니다. "
            "History 기능이 없어 전에 질문했던 내용은 기억하지 못합니다. "
        ),
        examples=[
            f"{demo_cves[0]}은 어떤 종류의 취약점인가요?",
            f"{demo_cves[1] if len(demo_cves) > 1 else demo_cves[0]}을 개발자가 예방하려면 어떻게 해야 하나요?",
            f"{demo_cves[2] if len(demo_cves) > 2 else demo_cves[0]}과 비슷한 실제 사고 사례가 있나요?",
        ],
        # show_error=True가 없으면 예외가 나도 화면에는 'Error' 한 단어만 뜬다.
        # 원인을 알 수 없어 디버깅이 매우 어려워지므로 교육용에서는 켜 두는 편이 낫다.
    ).launch(share=share, show_error=True)


def main() -> None:
    """이 파일의 시작점. 명령줄 인자를 보고 한 건만 조회할지 데모를 돌릴지 정한다.

    두 가지 실행 방식:
      1) 인자를 준 경우 -- 그 CVE 하나만 조회한다.
             python src/3_query.py CVE-2021-44228
             python src/3_query.py CVE-2021-44228 "how do I prevent this?"
         질문을 생략하면 DEFAULT_QUESTION이 쓰인다.

      2) 인자가 없는 경우 -- 데이터에서 CVE 세 개를 골라 서로 다른 질문으로
         검색해 보여준다. 처음 써보는 사람이 아무것도 몰라도
         `python src/3_query.py`만 치면 동작을 볼 수 있게 한 것이다.

      3) --ui를 준 경우 -- gradio 챗봇을 웹 브라우저에 띄운다.
             python src/3_query.py --ui
             python src/3_query.py --ui --share   # 외부 공유 주소까지 생성
         이때는 검색 결과만 보여주는 게 아니라 LLM이 답변까지 만들어 준다.

    sys.argv가 뭔가:
      프로그램을 실행할 때 명령줄에 적은 단어들이 담긴 리스트다.

          python src/3_query.py CVE-2021-44228 "how do I prevent this?"
          sys.argv = ['src/3_query.py', 'CVE-2021-44228', 'how do I prevent this?']

      맨 앞([0])은 항상 스크립트 파일 이름이라 우리에게 필요 없다. 그래서
      sys.argv[1:]로 그 뒤부터 잘라 쓴다. 따옴표로 감싼 문장은 공백이 있어도
      하나의 인자로 들어온다.

      0_fetch_real_data.py는 옵션이 많아 argparse를 썼지만, 여기는 인자가
      두 개뿐이라 직접 읽는 편이 더 간단하다. 도구는 상황에 맞게 고르면 된다.

    args[1]을 조건부로 읽는 이유:
      question = args[1] if len(args) > 1 else DEFAULT_QUESTION
      질문을 생략하고 CVE만 준 경우 args[1]이 없어서 그냥 읽으면 IndexError로
      죽는다. 먼저 개수를 확인하고 없으면 기본값을 쓴다.

    데모에서 collection을 미리 여는 이유:
      collection = get_collection()을 한 번 부른 뒤 answer_for_cve에 넘겨준다.
      이렇게 하면 CVE 세 건을 조회하는 동안 벡터 DB를 한 번만 열면 된다.
      안 넘기면 매번 DB를 다시 열고 TF-IDF의 경우 pickle까지 다시 읽는다.

    zip으로 CVE와 질문을 짝짓는 부분:
      for cve_id, question in zip(pick_demo_cves(), demo_questions):
      CVE 목록과 질문 목록을 앞에서부터 하나씩 짝지어 돈다. zip은 둘 중 짧은
      쪽에 맞춰 멈추므로, 데이터가 적어 CVE가 두 개만 나와도 에러 없이
      두 번만 돌고 끝난다. 안전한 성질이다.

    질문을 일부러 다르게 준 이유:
      "왜 위험한가", "개발자는 어떻게 막아야 하나", "실제 사고 사례가 있나"
      세 가지를 던진다. 같은 CWE 문서라도 질문에 따라 정의 섹션, 완화 방법
      섹션, 사례 섹션이 각각 걸리는 것을 보여주기 위해서다. 섹션 단위로
      청크를 나눈 1_chunk.py의 설계가 실제로 효과가 있는지 눈으로 확인할 수 있다.
    """
    args = sys.argv[1:]

    # --ui 또는 --share가 있으면 명령줄 조회 대신 웹 챗봇을 띄운다.
    if "--ui" in args or "--share" in args:
        launch_ui(share="--share" in args)
        return

    if args:
        cve_id = args[0]
        question = args[1] if len(args) > 1 else DEFAULT_QUESTION
        answer_for_cve(cve_id, question)
        return

    # 인자가 없으면 실데이터에서 CVE를 골라 데모를 돌린다.
    collection = get_collection()
    demo_questions = [
        "why is this dangerous and how do I prevent it?",
        "what are the recommended mitigations for developers?",
        "what real-world incidents came from this weakness?",
    ]
    for cve_id, question in zip(pick_demo_cves(), demo_questions):
        answer_for_cve(cve_id, question, collection=collection)


# `python src/3_query.py`로 직접 실행할 때만 main()이 호출된다.
if __name__ == "__main__":
    main()
