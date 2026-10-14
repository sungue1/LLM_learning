# Colab에서 glaive 어댑터로 답변 생성하기

`glaive.md`로 학습한 LoRA 어댑터를 Colab에서 불러와, 학습한 모델과 원래 Qwen의 답을 비교하고 Gradio 웹 화면으로 질문해 보는 과정입니다. 학습은 하지 않습니다. 아래 단계의 코드를 Colab 셀에 하나씩 붙여 넣고 차례로 실행하면 됩니다. 각 코드는 `fine_tun_local_infer.ipynb`의 코드 셀과 순서, 내용이 똑같으므로 노트북 파일을 Colab에 올려 그대로 실행해도 됩니다.

## 시작하기 전에

**필요한 것**
- Google 계정 (Colab 무료 사용 가능)
- `glaive.md` 20단계에서 내려받은 **`qwen-glaive-python.zip`** (약 29MB). 로컬 WSL에서 학습했다면 아래 명령으로 만들 수 있습니다. 만든 zip을 Windows 탐색기 주소창에 `\\wsl$\Ubuntu-24.04\home\salee\fine-tuning`을 넣어 찾아 Windows 쪽으로 복사해 두세요.

```bash
cd /home/salee/fine-tuning
python3 -c "import shutil; shutil.make_archive('qwen-glaive-python', 'zip', 'qwen-glaive-python')"
```

- Hugging Face 계정은 **필요 없습니다.** 원래 모델과 데이터셋 모두 로그인 없이 받을 수 있는 공개 저장소입니다.

**걸리는 시간:** 설치, 데이터 선택, 모델 내려받기를 합쳐 5~10분입니다. 답 하나는 T4에서 수십 초 걸릴 수 있습니다. T4에서 직접 재 보지는 않았습니다.

**Colab 준비**
1. [colab.research.google.com](https://colab.research.google.com)에서 **새 노트**를 만듭니다. 노트북 파일을 그대로 쓰려면 **파일 > 노트 업로드**로 `fine_tun_local_infer.ipynb`를 올립니다.
2. 메뉴 **런타임 > 런타임 유형 변경**에서 하드웨어 가속기를 **T4 GPU**로 고르고 저장합니다.
3. 아래 단계를 차례로 실행합니다. 셀 실행은 `Shift+Enter`입니다.

학습을 **같은 Colab 노트**에서 방금 끝냈다면 어댑터 폴더가 이미 있어서 zip을 올릴 필요가 없습니다. 이때도 1~4단계는 그대로 실행하세요. 설치는 이미 된 상태라 금방 끝납니다.

**예상 결과에 대해:** 아래 예상 결과는 로컬 GTX 1650에서 실제로 나온 출력입니다. T4에서는 GPU 이름이 다르고, 답의 문장이 조금 달라질 수 있습니다.

## 준비

Colab 환경을 맞추고 학습한 어댑터를 올립니다.

### 1단계. 라이브러리 설치 (Colab 전용)

Colab에는 transformers, datasets 같은 라이브러리가 미리 깔려 있지만 버전이 이 노트북을 만든 버전과 다릅니다. 그래서 검증된 버전으로 고정해 설치합니다. 고정하지 않으면 두 가지 문제가 생깁니다.

- **학습 설정에서 멈춤.** 최신 transformers(5.x)와 trl(1.x)에서는 `warmup_ratio` 인자가 없어져 `TypeError`가 납니다.
- **CUDA 버전 불일치.** bitsandbytes는 torch가 쓰는 CUDA 버전과 정확히 맞는 파일만 불러옵니다. Colab의 torch가 올라가면 맞는 파일이 없어 아래 같은 오류가 납니다.

```text
RuntimeError: Configured CUDA binary not found at
  .../bitsandbytes/libbitsandbytes_cuda130.so
```

그래서 torch도 함께 고정합니다. torch는 PyPI 기본 휠이 CPU 전용이라 전용 인덱스에서 받고, 나머지는 PyPI에서 받으므로 설치 명령을 두 번 실행합니다. torch 휠이 약 2.5GB라 2~4분 걸립니다.

설치 중 빨간 글씨로 "dependency conflicts"(의존성 충돌) 경고가 나올 수 있습니다. Colab에 깔린 다른 패키지가 최신 버전을 원한다는 뜻이고, 이 노트북과는 관계없으니 무시해도 됩니다. **"세션 다시 시작"(Restart session) 안내가 뜨면 누른 뒤, 이 셀은 건너뛰고 2단계부터 실행하세요.**

```python
import subprocess
import sys

try:
    import google.colab  # noqa: F401
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

# Colab의 torch 버전은 수시로 바뀝니다. bitsandbytes는 torch가 쓰는 CUDA 버전과
# 정확히 맞는 파일만 불러오므로, torch까지 검증된 버전으로 고정합니다.
TORCH = ["torch==2.5.1+cu121", "--index-url", "https://download.pytorch.org/whl/cu121"]

PACKAGES = [
    "transformers==4.55.2",
    "peft==0.17.0",
    "bitsandbytes==0.47.0",
    "accelerate==1.10.0",
    "datasets==4.0.0",
    "huggingface-hub<1.0",
    "gradio==6.17.3",
]

if IN_COLAB:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *TORCH], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *PACKAGES], check=True)
    print("설치 완료")
else:
    print("로컬 환경이라 설치를 건너뜁니다.")
```

예상 결과:

````text
설치 완료
````

### 2단계. 라이브러리 불러오기와 버전 확인

라이브러리를 불러오고, 1단계에서 고정한 transformers 버전이 실제로 쓰이는지 확인합니다. 다르면 오류로 멈추니, 메뉴 **런타임 > 세션 다시 시작**을 누르고 이 셀부터 다시 실행하세요.

마지막 줄에서 bitsandbytes를 불러옵니다. torch의 CUDA 버전과 맞는 파일이 없으면 모델을 적재하기 전에 여기서 바로 드러납니다.

```python
import os

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import re
import shutil
import torch
import pandas as pd
import transformers
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftConfig, PeftModel

print("torch", torch.__version__, "| CUDA", torch.version.cuda)
print("transformers", transformers.__version__)
if transformers.__version__ != "4.55.2":
    raise RuntimeError("라이브러리 버전이 다릅니다. Colab 메뉴 '런타임 > 세션 다시 시작'을 누른 뒤 이 셀부터 다시 실행하세요.")

# torch의 CUDA 버전과 맞는 파일이 없으면 여기서 바로 오류가 납니다.
import bitsandbytes
print("bitsandbytes", bitsandbytes.__version__)
```

예상 결과:

````text
torch 2.5.1+cu121 | CUDA 12.1
transformers 4.55.2
bitsandbytes 0.47.0
````

### 3단계. 어댑터 고르기와 GPU 확인

쓸 어댑터를 고릅니다. 이 안내서는 glaive 어댑터(`qwen-glaive-python`)를 기준으로 하므로 그 줄만 주석이 풀려 있습니다. 다른 어댑터를 쓰려면 맨 아래 "다른 어댑터 쓰기"를 보세요.

GPU가 없으면 "GPU가 없습니다" 오류로 멈춥니다. 메뉴 **런타임 > 런타임 유형 변경**에서 **T4 GPU**를 고르고 1단계부터 다시 실행하세요.

```python
# 쓸 어댑터 하나만 주석을 푸세요. 데이터와 프롬프트는 이 값에 맞춰 자동으로 바뀝니다.
#ADAPTER_DIR = "qwen-python-answers"    # fine_tun_local.ipynb
ADAPTER_DIR = "qwen-glaive-python"   # fine_tun_glaive.ipynb
#ADAPTER_DIR = "qwen-koalpaca"        # fine_tun_koalpaca.ipynb

if not torch.cuda.is_available():
    raise RuntimeError("GPU가 없습니다. Colab 메뉴 '런타임 > 런타임 유형 변경'에서 T4 GPU를 고르세요.")
print(torch.cuda.get_device_name(0))
```

예상 결과:

````text
Tesla T4
````

### 4단계. 학습한 어댑터 올리기

Colab에는 학습한 어댑터 폴더가 없습니다. 폴더가 없으면 파일 선택 창이 뜨니, 학습 노트북(`glaive.md` 20단계)에서 내려받은 **`qwen-glaive-python.zip`**을 고르세요. 약 29MB라 올리는 데 조금 걸립니다. 올린 zip은 `qwen-glaive-python` 폴더에 자동으로 풀립니다.

학습을 **같은 Colab 노트**에서 방금 끝냈다면 폴더가 이미 있으므로 창이 뜨지 않고 바로 넘어갑니다.

마지막 줄은 어댑터 설정 파일에서 원래 모델 이름을 읽습니다. 학습 때와 같은 원래 모델을 써야 어댑터가 맞게 얹히기 때문입니다.

```python
# Colab에는 학습한 어댑터 폴더가 없으므로, 학습 노트북에서 내려받은 zip을 올려 풉니다.
if not os.path.isdir(ADAPTER_DIR):
    if not IN_COLAB:
        raise FileNotFoundError(f"{ADAPTER_DIR} 폴더가 없습니다. 먼저 학습 노트북을 실행하세요.")
    from google.colab import files
    print(f"{ADAPTER_DIR}.zip 파일을 고르세요.")
    uploaded = files.upload()
    shutil.unpack_archive(next(iter(uploaded)), ADAPTER_DIR)

# 어댑터가 어떤 베이스 모델로 학습됐는지는 adapter_config.json에 적혀 있습니다.
BASE_MODEL = PeftConfig.from_pretrained(ADAPTER_DIR).base_model_name_or_path
print(ADAPTER_DIR, "->", BASE_MODEL)
```

예상 결과:

````text
qwen-glaive-python.zip 파일을 고르세요.
(파일 선택 후)
qwen-glaive-python -> Qwen/Qwen2.5-1.5B-Instruct
````

## 데이터 준비

학습 때 쓰지 않은 검증 질문을 학습 노트북과 같은 규칙으로 다시 고릅니다.

### 5단계. 프롬프트 만들기

학습 때와 똑같은 프롬프트를 만듭니다. Python 어댑터 두 개는 질문 앞에 지시 문구("Get answers for questions related to Python...")를 붙여 학습했고, KoAlpaca는 질문만 넣어 학습했습니다. `ADAPTER_DIR`에 따라 자동으로 고릅니다.

```python
PYTHON_PREFIX = "Get answers for questions related to Python. Respond with answers, no explanation\n\n"

def prompt_for(question):
    # KoAlpaca는 지시 문구 없이 질문만 넣고 학습했습니다.
    if ADAPTER_DIR == "qwen-koalpaca":
        return [{"role": "user", "content": question}]
    return [{"role": "user", "content": PYTHON_PREFIX + question}]
```

### 6단계. 토크나이저와 검증 샘플 고르는 함수

토크나이저를 불러오고, 학습 노트북과 똑같은 규칙으로 샘플을 고르는 함수를 만듭니다.

- `fits`: 채팅 템플릿을 포함해 256토큰 이하인지 봅니다. 템플릿을 문자열로 만든 뒤 토큰으로 나누므로, transformers 버전에 따라 결과가 달라지지 않습니다.
- `pick_val_set`: 섞인 순서대로 조건에 맞는 샘플을 600건 모은 뒤, 학습에 쓴 앞 500건을 건너뛰고 뒤 100건을 돌려줍니다. 그래서 학습 때 보지 못한 질문만 나옵니다.

```python
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR)

def fits(item, max_length=256):
    # 템플릿을 문자열로 만든 뒤 토큰으로 나눕니다. transformers 버전에 따라 결과가 달라지지 않습니다.
    messages = prompt_for(item["question"]) + [{"role": "assistant", "content": item["answer"]}]
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    return len(tokenizer(text, add_special_tokens=False)["input_ids"]) <= max_length

def pick_val_set(rows, train_size=500, val_size=100, dedup=False):
    # 학습 노트북과 같은 규칙으로 고른 뒤, 학습에 쓴 앞쪽 500건 다음의 100건을 돌려줍니다.
    selected, seen = [], set()
    for item in rows:
        if dedup:
            question = item["question"].strip()
            if question in seen:
                continue
            seen.add(question)
        if fits(item):
            selected.append(item)
            if len(selected) == train_size + val_size:
                break
    return selected[train_size:]
```

### 7단계. 검증 데이터 불러오기

어댑터에 맞는 데이터셋을 불러와 검증 샘플 100건을 고릅니다. glaive는 데이터셋(약 200MB)을 로그인 없이 내려받은 뒤 Python 질문만 남기고, 학습 때와 같은 `seed=42` 순서로 고릅니다. 30초~1분 걸립니다.

Colab이 "HF_TOKEN 시크릿이 없다"는 경고를 띄울 수 있지만 공개 데이터셋이라 그대로 받아집니다.

```python
if ADAPTER_DIR == "qwen-python-answers":
    if IN_COLAB and not os.path.exists("data/python_qa.csv"):
        # Colab에는 python_qa.csv가 없으므로 로컬의 data/python_qa.csv를 올립니다.
        from google.colab import files
        os.makedirs("data", exist_ok=True)
        print("python_qa.csv 파일을 고르세요.")
        uploaded = files.upload()
        shutil.move(next(iter(uploaded)), "data/python_qa.csv")
    qna_df = pd.read_csv("data/python_qa.csv")
    qa_format = [{"question": q, "answer": a} for q, a in zip(qna_df["Body"], qna_df["Answer"])]
    val_set = qa_format[3001:3101]

elif ADAPTER_DIR == "qwen-glaive-python":
    rows = load_dataset("glaiveai/glaive-code-assistant", split="train")
    rows = rows.filter(lambda item: "python" in item["question"].lower())
    val_set = pick_val_set(rows.shuffle(seed=42))

elif ADAPTER_DIR == "qwen-koalpaca":
    URL = re.compile(r"https?://")
    SENTENCE_END = re.compile(r"[.!?…)\]\"'다요죠음됨함]\s*$")
    rows = load_dataset("beomi/KoAlpaca-v1.1a", split="train")
    rows = rows.filter(lambda item: not URL.search(item["output"].strip())
                       and bool(SENTENCE_END.search(item["output"].strip())))
    rows = rows.rename_columns({"instruction": "question", "output": "answer"})
    val_set = pick_val_set(rows.shuffle(seed=42), dedup=True)

else:
    raise ValueError(f"데이터를 모르는 어댑터입니다: {ADAPTER_DIR}")

len(val_set)
```

예상 결과:

````text
100
````

### 8단계. 검증 첫 샘플 보기

검증 첫 샘플입니다. 학습 노트북의 검증 첫 질문과 같다면 샘플이 제대로 골라진 것입니다. 답변은 glaive 데이터셋의 답인데, 모델이 생성한 답이라 정답이라는 보장은 없습니다. 이 답도 코드가 4와 8만 만들어 틀렸습니다.

```python
val_set[0]
```

예상 결과:

````text
{'question': 'How can I create a list in Python that stores the first 10 numbers divisible by 4?',
 'answer': "You can use list comprehension in Python to create such a list. ..."}
````

## 모델 적재

원래 모델을 4비트로 올리고 학습한 어댑터를 얹습니다.

### 9단계. 4비트 양자화 설정

학습 때와 같이 원래 모델을 4비트(NF4)로 줄여 올리는 설정입니다. 어댑터는 4비트로 올린 모델 위에서 학습됐으므로, 같은 방식으로 올려야 결과가 학습 때와 맞습니다. T4는 Turing 세대라 계산은 fp16으로 합니다.

```python
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
```

### 10단계. 모델과 어댑터 불러오기

원래 모델 Qwen2.5-1.5B-Instruct를 내려받아(약 3GB, 로그인 불필요) 4비트로 올리고, 그 위에 학습한 어댑터를 얹습니다. 1~2분 걸립니다.

`model.eval()`은 드롭아웃을 끕니다. 빠뜨리면 답이 "下面是小下面是小..."처럼 무너집니다. 끝의 세미콜론은 모델 구조가 길게 출력되는 것을 막습니다.

학습 노트북과 달리 `prepare_model_for_kbit_training`은 하지 않습니다. 추론에는 필요 없고 메모리만 더 씁니다.

```python
tokenizer.truncation_side = "left"   # 질문이 길면 앞을 자릅니다

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=quant_config,
    torch_dtype=torch.float16,
    device_map={"": 0},
)
model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
model.eval();   # 드롭아웃을 끕니다. 세미콜론은 모델 구조 출력을 막습니다.
```

### 11단계. GPU 메모리 확인

모델과 어댑터가 GPU 메모리를 얼마나 쓰는지 봅니다. 학습 때(1.50GB)보다 적은 것은 학습용 준비를 하지 않아서입니다.

```python
print("VRAM: %.2f GB" % (torch.cuda.memory_allocated() / 1024**3))
```

예상 결과:

````text
VRAM: 1.07 GB
````

## 답변 생성

학습한 모델, 원래 Qwen, 데이터셋의 답을 비교합니다.

### 12단계. 답변 생성 함수

질문을 받아 답을 만드는 함수입니다. 학습 때와 같은 프롬프트를 만들고, 최대 200토큰까지 생성합니다. `do_sample=False`라 같은 질문에는 매번 같은 답이 나옵니다.

생성할 때 "The following generation flags are not valid" 경고가 나올 수 있는데, 무시해도 됩니다.

```python
def answer_for(question, max_new_tokens=200):
    text = tokenizer.apply_chat_template(prompt_for(question), tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to("cuda")
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
```

### 13단계. 검증 질문 보기

비교에 쓸 검증 첫 질문을 꺼냅니다.

```python
item = val_set[0]
print(item["question"][:500])
```

예상 결과:

````text
How can I create a list in Python that stores the first 10 numbers divisible by 4?
````

### 14단계. 파인튜닝한 모델의 답

학습한 모델의 답입니다. glaive 데이터처럼 코드 뒤에 설명을 길게 붙이는 문체로 바뀌었습니다. 하지만 코드가 0, 4, 8만 만들어 답은 틀렸습니다. T4에서는 계산 순서가 달라 문장이 조금 다를 수 있습니다.

```python
print(answer_for(item["question"]))
```

예상 결과:

````text
To achieve this, you can use the following code:

```python
numbers = [i for i in range(10) if i % 4 == 0]
```
...
After executing this code, the variable `numbers` will store the desired list: `[0, 4, 8]`.
````

### 15단계. 원래 Qwen의 답

`disable_adapter()` 안에서는 어댑터가 꺼져 원래 Qwen이 됩니다. 모델을 다시 올리지 않고 학습 전과 비교할 수 있습니다. 원래 Qwen은 짧지만 4부터 40까지 올바르게 답했습니다.

```python
with model.disable_adapter():
    print(answer_for(item["question"]))
```

예상 결과:

````text
```python
numbers = [i for i in range(4, 41, 4)]
print(numbers)
```
This code creates a list of numbers from 4 to 40 (inclusive) that are divisible by 4 using a list comprehension and prints it.
````

### 16단계. 데이터셋의 답

데이터셋에 들어 있는 답입니다. 학습한 모델의 문체가 이 답과 닮아 있는 것을 볼 수 있습니다.

```python
print(item["answer"])
```

예상 결과:

````text
You can use list comprehension in Python to create such a list. Here's an example code snippet that accomplishes this:
...
````

### 17단계. 다른 검증 샘플 보기

세 번째 검증 샘플입니다. 폴더와 그 안의 파일을 다른 곳으로 복사하는 질문입니다.

```python
val_set[2]
```

예상 결과:

````text
{'question': 'Is there a way to automate the process of copying a folder and all its files to a different location using Python?',
 'answer': "Yes, you can achieve this using the `shutil` module in Python. ..."}
````

### 18단계. 다른 검증 질문의 답

세 번째 검증 질문에 대한 학습한 모델의 답입니다. 데이터셋의 답과 거의 같은 구성으로 `shutil.copytree`를 씁니다.

```python
print(answer_for(val_set[2]['question']))
```

예상 결과:

````text
Yes, you can achieve this by utilizing the `shutil` module in Python. Here's an example code snippet ...

shutil.copytree(src, dst)
...
````

### 19단계. 직접 질문하기 (영어)

데이터셋에 없는 질문도 넣어 볼 수 있습니다. 따옴표 안의 문장을 바꿔 원하는 질문을 하세요.

```python
print(answer_for("How do I remove duplicates from a list while keeping the order?"))
```

예상 결과:

````text
To remove duplicates from a list in Python and maintain the original order of elements, you can use the following code:

def remove_duplicates(lst):
    seen = set()
    return [x for x in lst if not (x in seen or seen.add(x))]
...
````

### 20단계. 직접 질문하기 (한국어)

glaive 어댑터는 영어 Python 질문으로 학습했지만, 원래 Qwen이 한국어를 할 줄 알아서 한국어 질문에도 한국어로 답합니다. 다만 사실 관계는 따로 확인하세요.

```python
print(answer_for("네이버는 무엇을 하는 회사인가요?"))
```

예상 결과:

````text
네이버는 한국의 인터넷 서비스 기업으로, 네트워크를 통해 제공하는 다양한 서비스와 제품들을 개발하고 판매합니다.
...
````

## 웹 화면 (Gradio)

질문을 입력하면 두 모델의 답을 나란히 보여 주는 웹 화면을 띄웁니다.

### 21단계. Gradio 불러오기

웹 화면을 만드는 Gradio를 불러옵니다.

```python
import gradio as gr
```

### 22단계. 비교 함수

질문 하나에 대해 학습한 모델과 원래 Qwen의 답을 차례로 만들어 둘 다 돌려줍니다. 답을 두 번 만들므로 T4에서도 질문 하나에 수십 초가 걸릴 수 있습니다.

```python
def compare(question):
    tuned = answer_for(question)
    with model.disable_adapter():
        base = answer_for(question)
    return tuned, base
```

### 23단계. 화면 설정

어댑터마다 화면 제목, 설명, 입력 칸 이름, 예시 질문을 정해 둔 표입니다. `ADAPTER_DIR`에 맞는 설정을 자동으로 고릅니다. 예시 질문을 바꾸려면 해당 어댑터의 `examples` 목록을 고치세요.

```python
UI_BY_ADAPTER = {
    "qwen-python-answers": {
        "title": "Python Q&A 비교: Stack Overflow 파인튜닝",
        "description": "python_qa.csv(2008~2016년 Stack Overflow 질문과 답변)로 학습한 어댑터입니다. 영어로 질문하세요.",
        "label": "Python 질문 (영어)",
        "examples": [
            "What are the best books to learn Python?",
            "How do I read a file line by line in Python?",
        ],
    },
    "qwen-glaive-python": {
        "title": "Python Q&A 비교: glaive-code-assistant 파인튜닝",
        "description": "glaive-code-assistant의 Python 질문과 답변으로 학습한 어댑터입니다. 영어로 질문하세요.",
        "label": "Python 질문 (영어)",
        "examples": [
            "How can I sort a list of dictionaries by a value in Python?",
            "What is the difference between a list and a tuple in Python?",
        ],
    },
    "qwen-koalpaca": {
        "title": "한국어 Q&A 비교: KoAlpaca 파인튜닝",
        "description": "KoAlpaca-v1.1a(네이버 지식iN 질문과 ChatGPT 답변)로 학습한 어댑터입니다. 한국어로 질문하세요. 답의 사실 여부는 따로 확인하세요.",
        "label": "질문 (한국어)",
        "examples": [
            "겨울철 실내 습도를 적당히 유지하는 방법은 무엇인가요?",
            "바다는 왜 파란색으로 보이나요?",
        ],
    },
}
UI = UI_BY_ADAPTER[ADAPTER_DIR]
```

### 24단계. 웹 화면 띄우기

웹 화면을 띄웁니다. Colab에서는 출력에 `gradio.live`로 끝나는 공개 링크가 나옵니다. 그 링크를 눌러 새 탭에서 쓰는 것이 가장 안정적입니다. 입력 칸에 질문을 쓰거나 아래 예시를 누른 뒤 **Submit**을 누르면, 오른쪽에 두 모델의 답이 나란히 나옵니다. 답을 두 번 만들기 때문에 수십 초 기다려야 합니다.

**`share=IN_COLAB`이 중요합니다.** Colab에서 `share=False`로 두면 질문을 제출할 때 "Connection errored out" 또는 "Connecting to the server was lost"가 나옵니다. 화면은 보이지만, Gradio가 결과를 돌려줄 때 쓰는 실시간 연결이 Colab 내부 프록시를 통과하지 못하기 때문입니다. Gradio 자신도 호스팅 노트북에서는 `share=True`가 필요하다고 안내합니다. 로컬에서는 `IN_COLAB`이 False라 공개 링크를 만들지 않습니다.

공개 링크는 임의의 주소이고 최대 1주일 유지됩니다. 링크를 아는 사람은 누구나 접속할 수 있다는 점을 알아 두세요.

```python
demo = gr.Interface(
    fn=compare,
    inputs=gr.Textbox(label=UI["label"], lines=5),
    outputs=[
        gr.Textbox(label="파인튜닝한 Qwen"),
        gr.Textbox(label="원래 Qwen"),
    ],
    title=UI["title"],
    description=UI["description"],
    examples=UI["examples"],
    flagging_mode="never",
)
demo.launch(share=IN_COLAB)   # Colab에서는 공개 링크가 있어야 제출이 동작합니다
```

예상 결과:

````text
Colab: * Running on public URL: https://xxxxxxxx.gradio.live
로컬:  * Running on local URL:  http://127.0.0.1:7860
````

**링크를 잠그려면** 아이디와 비밀번호를 주면 됩니다. 접속하면 로그인 창이 먼저 뜹니다.

```python
demo.launch(share=IN_COLAB, auth=("myid", "mypassword"))
```

### 25단계. 웹 화면 닫기

다 쓴 뒤 웹 서버를 닫습니다. 24단계를 다시 실행하기 전에도 먼저 닫으세요. 닫지 않으면 7861처럼 다음 포트로 서버가 하나 더 뜹니다.

```python
demo.close()
```

예상 결과:

````text
Closing server running on port: 7860
````

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 2단계에서 "라이브러리 버전이 다릅니다" | 설치 전에 불러온 예전 버전이 메모리에 남아 있음 | **런타임 > 세션 다시 시작** 후 2단계부터 다시 실행 |
| 3단계에서 "GPU가 없습니다" | 런타임이 CPU로 되어 있음 | **런타임 > 런타임 유형 변경**에서 T4 GPU 선택 후 1단계부터 다시 실행 |
| 4단계에서 파일 선택 창이 안 뜸 | 브라우저가 팝업이나 서드파티 쿠키를 막음 | 왼쪽 파일 탭(폴더 아이콘)에 zip을 끌어다 놓은 뒤, 새 셀에서 `shutil.unpack_archive("qwen-glaive-python.zip", "qwen-glaive-python")` 실행 |
| 4단계에서 `adapter_config.json`을 찾을 수 없음 | zip 대신 다른 파일을 올렸거나, 폴더째 한 번 더 묶인 zip을 올림 | 파일 탭에서 `qwen-glaive-python` 폴더를 지우고, 학습 노트북이 만든 zip으로 다시 실행 |
| 1단계에서 빨간 "dependency conflicts" 경고 | Colab의 다른 패키지가 최신 버전을 원함 | 무시해도 됩니다 |
| bitsandbytes에서 `Configured CUDA binary not found ... libbitsandbytes_cuda1xx.so` | Colab의 torch가 쓰는 CUDA 버전과 bitsandbytes에 들어 있는 파일이 다름 | 1단계에서 torch까지 고정해 설치(이 안내서의 1단계 코드). 이미 실행했다면 **런타임 > 세션 다시 시작** 후 1단계부터 |
| torch를 고정하기 싫거나 설치가 너무 오래 걸림 | Colab 기본 torch를 그대로 쓰고 싶은 경우 | 1단계에서 TORCH 설치 줄을 빼고 `"bitsandbytes==0.47.0"`을 `"bitsandbytes"`로 바꿔 최신 버전 설치. 최신 bitsandbytes는 CUDA 13까지 지원하지만, 이 조합은 검증하지 않았습니다 |
| 답이 "下面是小下面是小..."처럼 무너짐 | 모델이 train 모드로 남음 | 10단계의 `model.eval()`이 실행됐는지 확인 |
| 질문을 제출하면 "Connection errored out" 또는 "Connecting to the server was lost" | Colab에서 `share=False`로 띄움. 결과를 돌려주는 실시간 연결이 Colab 내부 프록시를 통과하지 못함 | 24단계를 `demo.launch(share=IN_COLAB)`로 실행하고, 출력의 `gradio.live` 공개 링크에서 사용 |
| 공개 링크가 열리지 않거나 만료됨 | 링크는 최대 1주일만 유지됨 | `demo.close()` 후 24단계를 다시 실행해 새 링크 받기 |

## 다른 어댑터 쓰기

3단계에서 쓰려는 어댑터 줄의 주석을 풀고 나머지 줄은 주석 처리한 뒤, 세션을 다시 시작하고 1단계부터 실행합니다. 데이터, 프롬프트, 화면 설정은 자동으로 바뀝니다.

| 어댑터 | 4단계에서 올릴 파일 | 추가로 필요한 것 |
|---|---|---|
| `qwen-koalpaca` | `qwen-koalpaca.zip` | 없음. 데이터셋은 로그인 없이 받아집니다 |
| `qwen-python-answers` | `qwen-python-answers.zip` | 7단계에서 파일 선택 창이 한 번 더 뜨면 로컬의 `data/python_qa.csv`를 올립니다 |

로컬 어댑터 폴더를 zip으로 만드는 방법은 위 "시작하기 전에"의 명령에서 폴더 이름만 바꾸면 됩니다. 두 어댑터 모두 로컬에서 학습한 결과이고, Colab에서 다시 학습하는 노트북은 아직 없습니다.
