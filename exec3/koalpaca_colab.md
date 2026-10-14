# Colab에서 KoAlpaca 데이터로 Qwen2.5 한국어 파인튜닝하기

Qwen2.5-1.5B-Instruct를 KoAlpaca-v1.1a의 한국어 질문 500건으로 QLoRA 학습하는 과정입니다. 아래 단계의 코드를 Colab 셀에 하나씩 붙여 넣고 차례로 실행하면 됩니다. 각 코드는 `fine_tun_koalpaca.ipynb`의 코드 셀과 순서, 내용이 똑같으므로 노트북 파일을 Colab에 올려 그대로 실행해도 됩니다.

## 시작하기 전에

**필요한 것**
- Google 계정 (Colab 무료 사용 가능)
- Hugging Face 계정은 **필요 없습니다.** 원래 모델과 데이터셋 모두 로그인 없이 받을 수 있는 공개 저장소입니다.

**걸리는 시간**
- 라이브러리 설치와 내려받기: 5분 안팎
- 학습: 로컬 GTX 1650에서 약 1시간이 걸렸습니다. T4는 더 빠릅니다.

**이 학습으로 기대할 것과 기대하지 말 것**

말투와 형식은 바뀝니다. 원래 Qwen이 붙이던 불필요한 거절이나 일본어 섞인 답이 줄고, 한국어로 자연스럽게 답합니다. 하지만 **사실 정확도는 나아지지 않습니다.** 데이터의 답변 자체가 ChatGPT가 2023년에 생성한 글이라 검증되지 않은 내용이 섞여 있고, 1.5B 모델에 500건으로는 지식이 채워지지 않습니다.

데이터셋 카드에 라이선스 표기가 없습니다. 네이버 지식iN 게시물과 OpenAI 모델 출력에서 나온 데이터이므로 개인 학습 용도로만 쓰시길 권합니다.

**Colab 준비**
1. [colab.research.google.com](https://colab.research.google.com)에서 **새 노트**를 만듭니다. 노트북 파일을 그대로 쓰려면 **파일 > 노트 업로드**로 `fine_tun_koalpaca.ipynb`를 올립니다.
2. 메뉴 **런타임 > 런타임 유형 변경**에서 하드웨어 가속기를 **T4 GPU**로 고르고 저장합니다.
3. 아래 단계를 차례로 실행합니다. 셀 실행은 `Shift+Enter`입니다.

**예상 결과에 대해:** 아래 예상 결과는 로컬 GTX 1650에서 실제로 나온 출력입니다. T4에서는 GPU 이름이 다르고, 답의 문장이 조금 달라질 수 있습니다.

## 준비

Colab 환경을 맞춥니다.

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
    "trl==0.21.0",
    "bitsandbytes==0.47.0",
    "accelerate==1.10.0",
    "datasets==4.0.0",
    "huggingface-hub<1.0",
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

라이브러리를 불러오고, 1단계에서 고정한 버전이 실제로 쓰이는지 확인합니다. 다르면 오류로 멈추니, 메뉴 **런타임 > 세션 다시 시작**을 누르고 이 셀부터 다시 실행하세요.

마지막 줄에서 bitsandbytes를 불러옵니다. torch의 CUDA 버전과 맞는 파일이 없으면 학습까지 가지 않고 여기서 바로 드러나기 때문에, 문제를 일찍 발견할 수 있습니다.

`PYTORCH_CUDA_ALLOC_CONF`는 GPU 메모리 단편화를 줄이는 설정입니다. torch가 GPU를 처음 쓰기 전에 설정해야 효과가 있어서 import보다 먼저 둡니다.

```python
import os

# GPU 메모리 단편화를 줄입니다. 리눅스 전용이며, torch가 CUDA를 잡기 전에 설정해야 합니다.
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
import transformers
import trl
from datasets import Dataset, load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

print("torch", torch.__version__, "| CUDA", torch.version.cuda)
print("transformers", transformers.__version__, "| trl", trl.__version__)
if transformers.__version__ != "4.55.2" or trl.__version__ != "0.21.0":
    raise RuntimeError("라이브러리 버전이 다릅니다. 메뉴 '런타임 > 세션 다시 시작'을 누른 뒤 이 셀부터 다시 실행하세요.")

# torch의 CUDA 버전과 맞는 파일이 없으면 여기서 바로 오류가 납니다.
import bitsandbytes
print("bitsandbytes", bitsandbytes.__version__)
```

예상 결과:

````text
torch 2.5.1+cu121 | CUDA 12.1
transformers 4.55.2 | trl 0.21.0
bitsandbytes 0.47.0
````

### 3단계. 설정값과 GPU 확인

학습에 쓸 값을 정하고 GPU가 있는지 확인합니다.

| 설정 | 값 | 뜻 |
|---|---|---|
| `BASE_MODEL` | Qwen/Qwen2.5-1.5B-Instruct | 파인튜닝할 원래 모델 |
| `OUTPUT_DIR` | qwen-koalpaca | 학습 결과(어댑터)를 저장할 폴더 |
| `MAX_LENGTH` | 256 | 이보다 긴 샘플은 학습에서 뺍니다 |
| `TRAIN_SIZE` | 500 | 학습 샘플 수 |
| `VAL_SIZE` | 100 | 검증 샘플 수 |

"GPU가 없습니다" 오류가 나면 메뉴 **런타임 > 런타임 유형 변경**에서 **T4 GPU**를 고르고 저장한 뒤, 1단계부터 다시 실행하세요. 런타임을 바꾸면 설치한 라이브러리도 사라집니다.

```python
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
OUTPUT_DIR = "qwen-koalpaca"

# 원래 4GB GPU에 맞춘 길이입니다. 이보다 긴 샘플은 자르지 않고 아예 뺍니다.
MAX_LENGTH = 256

TRAIN_SIZE = 500
VAL_SIZE = 100

if not torch.cuda.is_available():
    raise RuntimeError("GPU가 없습니다. Colab 메뉴 '런타임 > 런타임 유형 변경'에서 T4 GPU를 고르세요.")
print(torch.cuda.get_device_name(0))
```

예상 결과:

````text
Tesla T4
````

## 데이터 준비

학습에 쓸 한국어 샘플을 고릅니다.

### 4단계. 데이터셋 내려받기

[beomi/KoAlpaca-v1.1a](https://huggingface.co/datasets/beomi/KoAlpaca-v1.1a)를 내려받습니다. 네이버 지식iN 베스트 질문을 모으고, 질문과 채택 답변을 참고 자료로 주어 ChatGPT가 답을 새로 쓴 데이터입니다. 약 13MB라 금방 받아집니다.

공개 데이터셋이라 Hugging Face 로그인 없이 받아집니다. Colab이 "HF_TOKEN 시크릿이 없다"는 경고를 띄워도 무시하세요. 다만 데이터셋 카드에 라이선스 표기가 없고, 지식iN 게시물과 OpenAI 모델 출력에서 나온 데이터라 개인 학습 용도로만 쓰시길 권합니다.

```python
raw = load_dataset("beomi/KoAlpaca-v1.1a", split="train")
raw
```

예상 결과:

````text
Dataset({
    features: ['instruction', 'output', 'url'],
    num_rows: 21155
})
````

### 5단계. 지저분한 답변 걸러 내기

링크가 들어 있거나 문장이 끝나지 않은 채 끝나는 답변을 뺍니다.

- **링크가 든 답변(약 1.4%).** 네이버나 Quora 링크가 그대로 들어간 답변입니다.
- **끝이 잘린 답변(약 2.4%).** 문장 끝이 마침표나 "다", "요" 같은 종결 어미로 끝나지 않는 답변입니다. 이 조건은 "- 호벗타이 -"처럼 원래 답변자의 서명이 붙은 답변도 함께 걸러 냅니다.

21,155건 중 20,539건이 남습니다.

```python
URL = re.compile(r"https?://")
SENTENCE_END = re.compile(r"[.!?…)\]\"'다요죠음됨함]\s*$")

def is_clean(item):
    answer = item["output"].strip()
    return not URL.search(answer) and bool(SENTENCE_END.search(answer))

clean_rows = raw.filter(is_clean)
len(raw), len(clean_rows)
```

예상 결과:

````text
(21155, 20539)
````

### 6단계. 프롬프트 만들기

질문을 사용자 메시지로, 답변을 어시스턴트 메시지로 둡니다. Python 노트북과 달리 지시 문구를 붙이지 않습니다. 지시 없이 질문만 받아도 한국어로 답하도록 배우는 것이 목표이기 때문입니다.

질문은 `prompt`, 답변은 `completion`으로 나눕니다. 이렇게 나누면 학습 라이브러리(TRL)가 답변 부분에만 손실을 걸어서, 모델이 질문을 외우지 않고 답하는 법만 배웁니다.

```python
def messages_for(item):
    return {
        "prompt": [{"role": "user", "content": item["instruction"]}],
        "completion": [{"role": "assistant", "content": item["output"]}],
    }
```

### 7단계. 토큰 길이 재는 함수

샘플 하나가 몇 토큰인지 셉니다. 실제 학습 입력과 똑같이 Qwen 채팅 템플릿을 붙인 뒤 셉니다.

템플릿을 먼저 문자열로 만든 다음 토큰으로 나눕니다. transformers 5.x에서는 템플릿 함수가 토큰을 바로 돌려줄 때 반환 형식이 바뀌어 길이가 항상 2로 잘못 계산되는데, 이 방식은 버전과 관계없이 같은 값을 냅니다.

한국어는 Qwen 토크나이저에서 토큰당 약 1.5글자입니다.

```python
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

def token_length(item):
    # 템플릿을 문자열로 만든 뒤 토큰으로 나눕니다. transformers 버전에 따라 결과가 달라지지 않습니다.
    m = messages_for(item)
    text = tokenizer.apply_chat_template(m["prompt"] + m["completion"], tokenize=False)
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])
```

### 8단계. 256토큰 이하 샘플 고르기

데이터를 섞은 뒤 앞에서부터 보면서 256토큰 이하인 것만 600건 모읍니다. 앞 500건은 학습용, 뒤 100건은 검증용입니다. 같은 질문이 두 번 나오면 처음 것만 씁니다.

긴 샘플을 자르지 않고 아예 빼는 이유는, 잘린 채 학습하면 답변의 끝부분을 배우지 못하기 때문입니다. KoAlpaca는 256토큰 이하가 약 34%(7,200건)라, glaive(약 8%)보다 고를 여지가 넓고 치우침도 덜합니다.

`seed=42`로 섞는 순서를 고정해서, 로컬에서 학습했을 때와 똑같은 샘플이 뽑힙니다.

```python
selected = []
seen_questions = set()
for item in clean_rows.shuffle(seed=42):
    question = item["instruction"].strip()
    if question in seen_questions:
        continue
    seen_questions.add(question)
    if token_length(item) <= MAX_LENGTH:
        selected.append(item)
        if len(selected) == TRAIN_SIZE + VAL_SIZE:
            break

train_set = selected[:TRAIN_SIZE]
val_set = selected[TRAIN_SIZE:]
len(train_set), len(val_set)
```

예상 결과:

````text
(500, 100)
````

### 9단계. 샘플 하나 살펴보기

검증용 첫 샘플이 학습 입력으로 어떻게 바뀌는지 봅니다. 로컬과 같은 샘플이 뽑혔다면 질문이 "컵라면을 최초로 만든 회사는 어디인가요?"입니다.

```python
messages_for(val_set[0])
```

예상 결과:

````text
{'prompt': [{'role': 'user', 'content': '컵라면을 최초로 만든 회사는 어디인가요?'}],
 'completion': [{'role': 'assistant',
   'content': "일본의 닛신식품에서 안도 모모후쿠(安藤百福) 회장이 인스턴트 라면을 발명하였습니다. ..."}]}
````

### 10단계. 학습용 데이터셋 만들기

고른 샘플을 학습 라이브러리가 읽는 `Dataset` 형식으로 바꿉니다.

```python
train_ds = Dataset.from_list([messages_for(item) for item in train_set])
val_ds = Dataset.from_list([messages_for(item) for item in val_set])
train_ds
```

예상 결과:

````text
Dataset({
    features: ['prompt', 'completion'],
    num_rows: 500
})
````

## 모델 적재

원래 모델을 4비트로 GPU에 올립니다.

### 11단계. 4비트 양자화 설정

모델 가중치를 4비트(NF4 형식)로 줄여서 GPU에 올리는 설정입니다. 이것이 QLoRA의 "Q"(Quantized)입니다. 1.5B 모델이 약 1GB로 줄어듭니다.

계산은 fp16으로 합니다. T4는 로컬의 GTX 1650과 같은 Turing 세대라 bf16을 하드웨어로 지원하지 않기 때문입니다.

```python
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
```

### 12단계. 모델 불러오기

Qwen2.5-1.5B-Instruct를 내려받아(약 3GB, 로그인 불필요) 4비트로 GPU에 올립니다. 1~2분 걸립니다.

`prepare_model_for_kbit_training`은 원래 가중치를 모두 얼리고, 학습 중 수치가 안정되도록 일부를 fp32로 바꾸고, 그래디언트 체크포인팅을 켭니다.

```python
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=quant_config,
    torch_dtype=torch.float16,
    device_map={"": 0},
)
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model.config.use_cache = False
```

### 13단계. GPU 메모리 확인

모델이 GPU 메모리를 얼마나 쓰는지 봅니다. 로컬 GTX 1650에서는 1.50GB였습니다.

```python
print("VRAM: %.2f GB" % (torch.cuda.memory_allocated() / 1024**3))
```

예상 결과:

````text
VRAM: 1.50 GB
````

## 학습

LoRA 어댑터를 학습합니다.

### 14단계. LoRA 설정

원래 가중치 15억 개는 그대로 두고, 어텐션의 네 층(q, k, v, o projection)에 작은 행렬 두 개씩(LoRA 어댑터)을 붙여 그것만 학습합니다. 학습되는 숫자는 약 218만 개로 전체의 0.14%입니다. 자세한 원리는 로컬 폴더의 `QLoRA.md`에 있습니다.

```python
peft_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
)
```

### 15단계. 학습 설정

학습 방법을 정합니다. Python 노트북과 같은 설정이라 결과를 서로 비교할 수 있습니다.

| 설정 | 값 | 뜻 |
|---|---|---|
| `completion_only_loss` | True | 답변 토큰에만 손실을 겁니다 |
| `num_train_epochs` | 1 | 학습 데이터를 한 바퀴만 봅니다 |
| `per_device_train_batch_size` | 1 | 한 번에 샘플 1개씩 계산합니다 |
| `gradient_accumulation_steps` | 8 | 8개를 모아 한 번 갱신합니다. 실질 배치는 8, 500건이면 63번 갱신 |
| `learning_rate` | 2e-4 | 최대 보폭. 처음 3%는 워밍업, 이후 코사인으로 줄어듭니다 |
| `fp16` | True | Turing GPU라 bf16 대신 fp16 |
| `optim` | paged_adamw_8bit | 옵티마이저 상태를 8비트로 저장하는 AdamW |
| `eval_strategy` | epoch | 학습이 끝날 때 검증 손실을 계산합니다 |

```python
train_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    max_length=MAX_LENGTH,
    completion_only_loss=True,      # 답변 토큰에만 손실을 겁니다
    num_train_epochs=1,
    per_device_train_batch_size=1,  # 2로 올리면 패딩 낭비로 오히려 느려집니다
    gradient_accumulation_steps=8,
    gradient_checkpointing=True,    # 끄면 메모리가 넘쳐 2배 느려집니다
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    fp16=True,                      # Turing 세대라 bf16은 못 씁니다
    optim="paged_adamw_8bit",
    logging_steps=10,
    eval_strategy="epoch",          # 에폭 끝에 검증 손실을 계산합니다
    per_device_eval_batch_size=1,
    save_strategy="epoch",
    report_to=[],
    seed=42,
)
```

### 16단계. 트레이너 만들기

모델, 학습 설정, 데이터, LoRA 설정을 묶어 트레이너를 만듭니다. 이때 데이터에 채팅 템플릿을 적용하고 토큰으로 바꾸는 작업이 진행됩니다.

```python
trainer = SFTTrainer(
    model=model,
    args=train_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    processing_class=tokenizer,
    peft_config=peft_config,
)
```

### 17단계. 학습 실행

학습을 시작합니다. 10스텝마다 학습 손실이 표에 찍히고, 끝나면 검증 손실이 나옵니다.

로컬 GTX 1650에서는 학습에 약 58분, 검증에 약 4분 걸렸습니다. T4는 더 빠릅니다. glaive 노트북을 Colab T4에서 돌렸을 때 손실 값이 로컬과 거의 같게 나왔으므로, 이 노트북도 아래와 비슷한 값이 나올 것으로 예상합니다.

| 스텝 | 학습 손실 |
|---|---|
| 10 | 2.04 |
| 30 | 1.96 |
| 60 | 1.96 |
| 검증 | 2.00 |

손실이 약 5%만 내려갑니다. 원래 Qwen이 이미 한국어를 어느 정도 하기 때문에 새로 배울 것이 적습니다. 말투는 바뀌지만 사실 정확도는 나아지지 않습니다.

Colab 무료 사용은 한동안 브라우저 탭을 조작하지 않으면 세션이 끊길 수 있습니다. 학습 중에는 탭을 열어 두세요.

```python
trainer.train()
```

예상 결과:

````text
TrainOutput(global_step=63, training_loss=1.983..., ...)
````

### 18단계. 최대 GPU 메모리 확인

학습 중 GPU 메모리를 가장 많이 썼을 때의 값입니다. 로컬에서는 2.58GB였습니다. T4의 16GB에는 여유가 많습니다.

```python
print("peak VRAM: %.2f GB" % (torch.cuda.max_memory_reserved() / 1024**3))
```

예상 결과:

````text
peak VRAM: 2.58 GB
````

## 결과 저장

학습 결과를 저장하고 밖으로 빼냅니다.

### 19단계. 어댑터 저장

학습한 LoRA 어댑터를 `qwen-koalpaca` 폴더에 저장합니다. 원래 모델 전체가 아니라 어댑터만 저장되므로 약 9MB입니다.

```python
trainer.save_model(OUTPUT_DIR)
```

### 20단계. 결과 저장 (Colab 전용)

Colab의 파일은 세션이 끝나면 모두 사라집니다. 저장한 폴더를 zip으로 묶어 밖으로 빼냅니다. 확인 단계에서 세션이 끊겨도 결과를 잃지 않도록, 확인보다 먼저 저장합니다.

방법은 두 가지이고 `SAVE_TO_DRIVE`로 고릅니다.

**`False` (기본값): 내 PC로 내려받기.** 브라우저의 다운로드 창이 뜹니다. 브라우저가 다운로드를 막으면 허용해 주세요. 파일 탭(왼쪽 폴더 아이콘)에서 `qwen-koalpaca.zip`을 오른쪽 클릭해 내려받아도 됩니다.

**`True`: Google Drive에 저장.** 셀을 실행하면 Google 계정 접근을 허용하라는 창이 뜹니다. 허용하면 Drive가 `/content/drive`에 연결되고, zip이 **내 드라이브 > fine-tuning** 폴더에 복사됩니다. 저장 위치는 `DRIVE_DIR`로 바꿉니다.

```python
# False면 내 PC로 내려받고, True면 Google Drive에 저장합니다.
SAVE_TO_DRIVE = True
DRIVE_DIR = "/content/drive/MyDrive/fine-tuning"

if IN_COLAB:
    zip_path = shutil.make_archive(OUTPUT_DIR, "zip", OUTPUT_DIR)
    if SAVE_TO_DRIVE:
        from google.colab import drive

        drive.mount("/content/drive")
        os.makedirs(DRIVE_DIR, exist_ok=True)
        print("Drive에 저장:", shutil.copy(zip_path, DRIVE_DIR))
    else:
        from google.colab import files

        files.download(f"{OUTPUT_DIR}.zip")
else:
    print("로컬 환경이라 저장을 건너뜁니다. 결과는", OUTPUT_DIR, "폴더에 있습니다.")
```

예상 결과:

````text
SAVE_TO_DRIVE = False 일 때: 브라우저의 다운로드 창이 뜹니다.

SAVE_TO_DRIVE = True 일 때:
Mounted at /content/drive
Drive에 저장: /content/drive/MyDrive/fine-tuning/qwen-koalpaca.zip
````

## 확인

학습한 모델과 원래 Qwen의 답을 비교합니다.

### 21단계. 추론 준비

학습한 모델로 답을 만들기 전에 추론 상태로 바꿉니다.

- `eval()`: 학습 직후의 모델은 train 모드라 LoRA 드롭아웃이 켜져 있습니다. 그대로 생성하면 출력이 무너집니다.
- `gradient_checkpointing_disable()`: 체크포인팅이 켜져 있으면 KV 캐시가 꺼져 생성이 매우 느려집니다.
- `truncation_side = "left"`: 질문이 너무 길면 앞부분을 자릅니다. 뒤를 자르면 프롬프트 끝의 답변 시작 표시가 잘려 나갑니다.

세션을 다시 시작했다면 학습을 다시 하지 않아도 됩니다. 메모리에 `trainer`가 없으면 저장된 어댑터를 불러옵니다. 단, Colab에서 세션이 완전히 끊겨 파일이 사라졌다면 내려받은 zip을 파일 탭에 올리고 `qwen-koalpaca` 폴더에 풀어야 합니다.

```python
if "trainer" in globals():
    # 방금 학습한 모델을 그대로 씁니다
    tuned_model = trainer.model
    tuned_model.gradient_checkpointing_disable()
else:
    # 커널을 재시작했으면 저장된 어댑터를 불러옵니다
    from peft import PeftModel
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=quant_config,
        torch_dtype=torch.float16,
        device_map={"": 0},
    )
    tuned_model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)

tuned_model.eval()                        # 드롭아웃을 끕니다
tuned_model.config.use_cache = True       # KV 캐시를 켜야 생성이 빠릅니다
tokenizer.truncation_side = "left"        # 질문이 길면 뒤가 아니라 앞을 자릅니다
```

### 22단계. 답변 생성 함수

질문을 받아 답을 만드는 함수입니다. 학습 때와 같이 지시 문구 없이 질문만 넣습니다. `do_sample=False`라 같은 질문에는 매번 같은 답이 나옵니다.

```python
def answer_for(question, max_new_tokens=200):
    prompt = [{"role": "user", "content": question}]
    text = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to("cuda")
    with torch.no_grad():
        output = tuned_model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
```

### 23단계. 비교 함수

질문 하나에 대해 학습한 모델과 원래 Qwen의 답을 만들어 나란히 출력합니다. `disable_adapter()` 안에서는 어댑터가 꺼져 원래 Qwen이 됩니다. 모델을 다시 올리지 않고 비교할 수 있습니다.

답을 두 번 만들므로 질문 하나에 수십 초가 걸릴 수 있습니다.

```python
def compare(question):
    tuned = answer_for(question)
    with tuned_model.disable_adapter():
        base = answer_for(question)
    print("■ 질문\n" + question)
    print("\n■ 원래 Qwen\n" + base)
    print("\n■ 파인튜닝한 Qwen\n" + tuned)
```

### 24단계. 검증 질문 비교 (1)

학습에 쓰지 않은 첫 검증 질문으로 비교합니다. 로컬 결과에서는 차이가 뚜렷했습니다. 원래 Qwen은 일본어 가타카나를 섞고 같은 문장을 되풀이하다 끊겼습니다. 학습한 모델은 한국어로만 짧게 답했습니다.

다만 학습한 모델의 답도 사실은 틀렸습니다. 컵라면은 1971년 닛신식품이 만들었는데 1920년대라고 답했습니다. 말투는 배웠지만 지식은 채워지지 않는다는 것을 보여 줍니다.

```python
compare(val_set[0]["instruction"])
print("\n■ 데이터의 답\n" + val_set[0]["output"])
```

예상 결과:

````text
■ 질문
컵라면을 최초로 만든 회사는 어디인가요?

■ 원래 Qwen
컵라면을 최초로 만든 회사 중 하나는 일본의 회사 "カプセルラーメン" (Kapshuuraam)입니다. ...

■ 파인튜닝한 Qwen
컵라면은 1920년대에 일본에서 만들어졌습니다. ...

■ 데이터의 답
일본의 닛신식품에서 안도 모모후쿠(安藤百福) 회장이 인스턴트 라면을 발명하였습니다. ...
````

### 25단계. 검증 질문 비교 (2)

두 번째 검증 질문입니다. 우측 운전석 차량이 국내에서 합법인지 묻습니다. 두 모델 모두 "문제없다"는 결론은 같지만, 근거로 드는 설명은 둘 다 엉성합니다.

```python
compare(val_set[1]["instruction"])
print("\n■ 데이터의 답\n" + val_set[1]["output"])
```

예상 결과:

````text
■ 질문
국내에서 우측 운전석을 가진 차량으로 운전해도 법적으로 문제가 없는가요?
...
````

### 26단계. 거절 표현 세기

원래 Qwen은 "저는 인공지능이라 알려드리기 어렵습니다"처럼 불필요한 거절이나 서두를 붙일 때가 있습니다. 검증 질문 10개로 그런 답이 얼마나 줄었는지 셉니다.

질문 하나에 답을 두 번 만들기 때문에 T4에서도 몇 분 걸립니다. 빨리 보고 싶으면 `COUNT_SIZE`를 3~5로 줄이세요.

로컬에서는 1개에서 0개로 줄었습니다. 질문 10개로 센 결과라 차이를 단정하기는 어렵습니다.

```python
REFUSAL = re.compile(r"인공지능|AI 모델|AI로서|언어 ?모델|죄송|알려드리기 어렵")
COUNT_SIZE = 10

tuned_count = base_count = 0
for item in val_set[:COUNT_SIZE]:
    tuned_count += bool(REFUSAL.search(answer_for(item["instruction"])))
    with tuned_model.disable_adapter():
        base_count += bool(REFUSAL.search(answer_for(item["instruction"])))

print(f"거절 표현이 들어간 답: 원래 Qwen {base_count}/{COUNT_SIZE}, 파인튜닝한 Qwen {tuned_count}/{COUNT_SIZE}")
```

예상 결과:

````text
거절 표현이 들어간 답: 원래 Qwen 1/10, 파인튜닝한 Qwen 0/10
````

### 27단계. 직접 질문하기

데이터에 없는 질문도 넣어 볼 수 있습니다. 괄호 안의 문장을 바꿔 원하는 질문을 하세요.

로컬에서는 두 모델 모두 습도를 **낮추는** 방법을 늘어놓아 질문의 취지를 놓쳤습니다. 겨울에는 보통 습도를 올려야 합니다. 학습 뒤에도 사실 정확도는 믿기 어렵다는 점을 보여 주는 예입니다.

```python
compare("겨울철 실내 습도를 적당히 유지하는 방법은 무엇인가요?")
```

예상 결과:

````text
■ 질문
겨울철 실내 습도를 적당히 유지하는 방법은 무엇인가요?
...
````

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 2단계에서 "라이브러리 버전이 다릅니다" | 설치 전에 불러온 예전 버전이 메모리에 남아 있음 | **런타임 > 세션 다시 시작** 후 2단계부터 다시 실행 |
| 3단계에서 "GPU가 없습니다" | 런타임이 CPU로 되어 있음 | **런타임 > 런타임 유형 변경**에서 T4 GPU 선택 후 1단계부터 다시 실행 |
| 1단계에서 빨간 "dependency conflicts" 경고 | Colab의 다른 패키지가 최신 버전을 원함 | 무시해도 됩니다 |
| "HF_TOKEN 시크릿이 없다"는 경고 | Hugging Face 로그인을 안 함 | 무시해도 됩니다. 공개 저장소라 그대로 받아집니다 |
| bitsandbytes에서 `Configured CUDA binary not found ... libbitsandbytes_cuda1xx.so` | Colab의 torch가 쓰는 CUDA 버전과 bitsandbytes에 들어 있는 파일이 다름 | 1단계에서 torch까지 고정해 설치(이 안내서의 1단계 코드). 이미 실행했다면 **런타임 > 세션 다시 시작** 후 1단계부터 |
| torch를 고정하기 싫거나 설치가 너무 오래 걸림 | Colab 기본 torch를 그대로 쓰고 싶은 경우 | 1단계에서 TORCH 설치 줄을 빼고 `"bitsandbytes==0.47.0"`을 `"bitsandbytes"`로 바꿔 최신 버전 설치. 최신 bitsandbytes는 CUDA 13까지 지원하지만, 이 조합은 검증하지 않았습니다 |
| 답이 무너지거나 같은 글자가 반복됨 | 추론 준비(21단계)를 건너뜀 | 21단계를 실행한 뒤 다시 생성 |
| 학습 도중 세션이 끊김 | Colab 무료 사용의 유휴 시간 제한 | 학습 중에는 탭을 열어 두기. 끊기면 1단계부터 다시 |

## 결과를 로컬에서 쓰기

20단계에서 내려받은 `qwen-koalpaca.zip`을 로컬 WSL의 `/home/salee/fine-tuning` 폴더로 옮긴 뒤 폴더에 풉니다. **기존 로컬 학습 결과를 덮어쓰므로**, 남겨 두려면 먼저 폴더 이름을 바꾸세요.

```bash
cd /home/salee/fine-tuning
mv qwen-koalpaca qwen-koalpaca-local   # 로컬 결과를 남겨 두려면
unzip -o qwen-koalpaca.zip -d qwen-koalpaca
```

그다음 `fine_tun_local_infer.ipynb`에서 `ADAPTER_DIR = "qwen-koalpaca"` 줄의 주석을 풀고 실행하면, Gradio 화면에서 원래 Qwen과 나란히 비교할 수 있습니다. 그 노트북을 Colab에서 쓰는 방법은 `glaive_infer.md`에 있습니다. 20단계에서 Drive에 저장했다면, 추론 노트북에서도 파일을 올리는 대신 Drive에서 바로 풀 수 있습니다.

```python
from google.colab import drive
drive.mount("/content/drive")
shutil.unpack_archive("/content/drive/MyDrive/fine-tuning/qwen-koalpaca.zip", "qwen-koalpaca")
```
