# Colab에서 glaive 데이터로 Qwen2.5 파인튜닝하기

Qwen2.5-1.5B-Instruct를 glaive-code-assistant의 Python 질문 500건으로 QLoRA 학습하는 과정입니다. 아래 단계의 코드를 Colab 셀에 하나씩 붙여 넣고 차례로 실행하면 됩니다. 각 코드는 `fine_tun_glaive.ipynb`의 셀과 똑같으므로, 노트북 파일을 Colab에 올려 그대로 실행해도 됩니다.

## 시작하기 전에

**필요한 것**
- Google 계정 (Colab 무료 사용 가능)
- Hugging Face 계정은 **필요 없습니다.** 모델과 데이터셋 모두 로그인 없이 받을 수 있는 공개 저장소이고, Apache 2.0 라이선스입니다.

**걸리는 시간**
- 라이브러리 설치와 내려받기: 5분 안팎
- 학습: 로컬 GTX 1650에서 약 1시간이 걸렸습니다. T4는 더 빠를 것으로 예상하지만 재 보지는 않았습니다.

**Colab 준비**
1. [colab.research.google.com](https://colab.research.google.com)에서 **새 노트**를 만듭니다. 노트북 파일을 그대로 쓰려면 **파일 > 노트 업로드**로 `fine_tun_glaive.ipynb`를 올립니다.
2. 메뉴 **런타임 > 런타임 유형 변경**에서 하드웨어 가속기를 **T4 GPU**로 고르고 저장합니다.
3. 아래 단계를 차례로 실행합니다. 셀 실행은 `Shift+Enter`입니다.

**왜 버전을 고정하나요?** Colab에 미리 깔린 최신 라이브러리(transformers 5.x, trl 1.x)로는 이 코드가 돌지 않습니다. 새 환경에 노트북 코드를 그대로 돌려 확인한 결과, 학습 설정에서 `TypeError`로 멈췄습니다. 그 앞 단계인 토큰 길이 계산도 오류 없이 틀린 값을 냈습니다. 그래서 1단계에서 이 PC(WSL)에서 검증한 버전으로 고정합니다.

## 준비

Colab 환경을 맞춥니다.

### 1단계. 라이브러리 설치 (Colab 전용)

Colab에는 transformers, datasets 같은 라이브러리가 미리 깔려 있지만 버전이 이 노트북을 만든 버전과 다릅니다. 최신 버전(transformers 5.x, trl 1.x)에서는 학습 설정 셀이 `warmup_ratio` 인자 때문에 `TypeError`로 멈춥니다. 그래서 이 PC(WSL)에서 검증한 버전으로 고정해 설치합니다. trl과 bitsandbytes는 Colab에 없어서 새로 설치됩니다.

이 셀은 Colab에서만 설치하고, 로컬에서는 아무것도 하지 않습니다.

설치 중 빨간 글씨로 "dependency conflicts"(의존성 충돌) 경고가 나올 수 있습니다. Colab에 깔린 다른 패키지가 최신 transformers를 원한다는 뜻이고, 이 노트북과는 관계없으니 무시해도 됩니다. **"세션 다시 시작"(Restart session) 버튼이나 안내가 뜨면 누른 뒤, 이 셀은 건너뛰고 2단계부터 다시 실행하세요.**

```python
import subprocess
import sys

try:
    import google.colab  # noqa: F401
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

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
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *PACKAGES], check=True)
    print("설치 완료")
else:
    print("로컬 환경이라 설치를 건너뜁니다.")
```

예상 결과:

```text
설치 완료
```

### 2단계. 라이브러리 불러오기와 버전 확인

라이브러리를 불러오고, 1단계에서 고정한 버전이 실제로 쓰이는지 확인합니다. 버전이 다르면 이 셀이 오류와 함께 멈춥니다. 1단계를 실행하기 전에 transformers를 이미 불러온 적이 있으면, 설치한 새 버전이 아니라 예전 버전이 메모리에 남아 있어서 생기는 일입니다. 이때는 메뉴 **런타임 > 세션 다시 시작**을 누른 뒤 이 2단계부터 다시 실행하세요.

`PYTORCH_CUDA_ALLOC_CONF`는 GPU 메모리 단편화를 줄이는 설정입니다. torch가 GPU를 처음 쓰기 전에 설정해야 효과가 있어서 import보다 먼저 둡니다.

```python
import os

# GPU 메모리 단편화를 줄입니다. torch가 CUDA를 잡기 전에 설정해야 합니다.
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
import transformers
import trl
from datasets import Dataset, load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

print("transformers", transformers.__version__, "| trl", trl.__version__)
if transformers.__version__ != "4.55.2" or trl.__version__ != "0.21.0":
    raise RuntimeError("라이브러리 버전이 다릅니다. 메뉴 '런타임 > 세션 다시 시작'을 누른 뒤 이 셀부터 다시 실행하세요.")
```

예상 결과:

```text
transformers 4.55.2 | trl 0.21.0
```

### 3단계. 설정값과 GPU 확인

학습에 쓸 값을 정하고 GPU가 있는지 확인합니다.

| 설정 | 값 | 뜻 |
|---|---|---|
| `BASE_MODEL` | Qwen/Qwen2.5-1.5B-Instruct | 파인튜닝할 원래 모델 |
| `OUTPUT_DIR` | qwen-glaive-python | 학습 결과(어댑터)를 저장할 폴더 |
| `MAX_LENGTH` | 256 | 이보다 긴 샘플은 학습에서 뺍니다 |
| `TRAIN_SIZE` | 500 | 학습 샘플 수 |
| `VAL_SIZE` | 100 | 검증 샘플 수 |

`MAX_LENGTH`는 원래 4GB GPU(GTX 1650)에 맞춘 값입니다. T4는 16GB라 더 늘릴 수 있지만, 로컬 결과와 비교하려면 그대로 두세요.

"GPU가 없습니다" 오류가 나면 메뉴 **런타임 > 런타임 유형 변경**에서 **T4 GPU**를 고르고 저장한 뒤, 1단계부터 다시 실행하세요. 런타임을 바꾸면 설치한 라이브러리도 사라집니다.

```python
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
OUTPUT_DIR = "qwen-glaive-python"

# 원래 4GB GPU에 맞춘 길이입니다. 이보다 긴 샘플은 자르지 않고 아예 뺍니다.
MAX_LENGTH = 256

TRAIN_SIZE = 500
VAL_SIZE = 100

if not torch.cuda.is_available():
    raise RuntimeError("GPU가 없습니다. Colab 메뉴 '런타임 > 런타임 유형 변경'에서 T4 GPU를 고르세요.")
print(torch.cuda.get_device_name(0))
```

예상 결과:

```text
Tesla T4
```

## 데이터 준비

학습에 쓸 샘플을 고릅니다.

### 4단계. 데이터셋 내려받기

[glaiveai/glaive-code-assistant](https://huggingface.co/datasets/glaiveai/glaive-code-assistant)를 내려받습니다. Stack Overflow식 코딩 질문과 답변 13만 6천 건으로 된 Apache 2.0 데이터셋입니다. 답변은 사람이 아니라 모델이 생성했습니다.

공개 데이터셋이라 Hugging Face 로그인 없이 받을 수 있습니다. Colab이 "HF_TOKEN 시크릿이 없다"는 경고를 띄울 수 있는데, 다운로드는 그대로 진행되니 무시하세요. 약 200MB라 1분 안팎 걸립니다.

```python
raw = load_dataset("glaiveai/glaive-code-assistant", split="train")
raw
```

예상 결과:

```text
Dataset({
    features: ['question', 'answer'],
    num_rows: 136109
})
```

### 5단계. Python 질문만 고르기

여러 언어의 질문이 섞여 있어서, 질문에 "python"이 들어간 것만 남깁니다.

```python
python_rows = raw.filter(lambda item: "python" in item["question"].lower())
len(python_rows)
```

예상 결과:

```text
49219
```

### 6단계. 프롬프트 만들기

질문 앞에 지시 문구("Get answers for questions related to Python...")를 붙여 사용자 메시지를 만들고, 답변을 어시스턴트 메시지로 둡니다. 원래 OpenAI 파인튜닝 노트북(`fine_tun.ipynb`)과 같은 문구입니다.

질문은 `prompt`, 답변은 `completion`으로 나눕니다. 이렇게 나누면 학습 라이브러리(TRL)가 답변 부분에만 손실을 걸어서, 모델이 질문을 외우지 않고 답하는 법만 배웁니다.

```python
def messages_for(item):
    message = f"Get answers for questions related to Python. Respond with answers, no explanation\n\n{item['question']}"
    return {
        "prompt": [{"role": "user", "content": message}],
        "completion": [{"role": "assistant", "content": item["answer"]}],
    }
```

### 7단계. 토큰 길이 재는 함수

샘플 하나가 몇 토큰인지 셉니다. 실제 학습 입력과 똑같이 Qwen 채팅 템플릿(시스템 메시지, 역할 표시 등)을 붙인 뒤 셉니다.

템플릿을 먼저 문자열로 만든 다음 토큰으로 나눕니다. transformers 5.x에서는 템플릿 함수가 토큰을 바로 돌려줄 때 반환 형식이 바뀌어 길이가 항상 2로 잘못 계산되는데, 이 방식은 버전과 관계없이 같은 값을 냅니다. 로컬에서 기존 방식과 비교해 모든 샘플의 길이가 같았습니다.

```python
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

def token_length(item):
    m = messages_for(item)
    text = tokenizer.apply_chat_template(m["prompt"] + m["completion"], tokenize=False)
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])
```

### 8단계. 256토큰 이하 샘플 고르기

데이터를 섞은 뒤 앞에서부터 보면서 256토큰 이하인 것만 600건 모읍니다. 앞 500건은 학습용, 뒤 100건은 검증용입니다.

긴 샘플을 자르지 않고 아예 빼는 이유는, 잘린 채 학습하면 답변의 끝부분을 배우지 못하고 질문이 길면 답변이 통째로 사라지기 때문입니다. 256토큰 이하는 Python 질문의 약 8%라서 짧고 기초적인 질문 위주로 뽑힌다는 점은 알아 두세요.

`seed=42`로 섞는 순서를 고정해서, 로컬에서 학습했을 때와 똑같은 샘플이 뽑힙니다. 약 7,800건을 훑어야 해서 30초 안팎 걸립니다.

```python
selected = []
for item in python_rows.shuffle(seed=42):
    if token_length(item) <= MAX_LENGTH:
        selected.append(item)
        if len(selected) == TRAIN_SIZE + VAL_SIZE:
            break

train_set = selected[:TRAIN_SIZE]
val_set = selected[TRAIN_SIZE:]
len(train_set), len(val_set)
```

예상 결과:

```text
(500, 100)
```

### 9단계. 샘플 하나 살펴보기

검증용 첫 샘플이 학습 입력으로 어떻게 바뀌는지 봅니다. 로컬과 같은 샘플이 뽑혔다면 질문이 아래와 같습니다.

```python
messages_for(val_set[0])
```

예상 결과:

```text
{'prompt': [{'role': 'user', 'content': 'Get answers for questions related to Python. ... How can I create a list in Python that stores the first 10 numbers divisible by 4?'}],
 'completion': [{'role': 'assistant', 'content': 'You can use list comprehension in Python to create such a list. ...'}]}
```

### 10단계. 학습용 데이터셋 만들기

고른 샘플을 학습 라이브러리가 읽는 `Dataset` 형식으로 바꿉니다.

```python
train_ds = Dataset.from_list([messages_for(item) for item in train_set])
val_ds = Dataset.from_list([messages_for(item) for item in val_set])
train_ds
```

예상 결과:

```text
Dataset({
    features: ['prompt', 'completion'],
    num_rows: 500
})
```

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

Qwen2.5-1.5B-Instruct를 내려받아 4비트로 GPU에 올립니다. 공개 모델이라 로그인 없이 받을 수 있고, 약 3GB라 1~2분 걸립니다.

`prepare_model_for_kbit_training`은 원래 가중치를 모두 얼리고, 학습 중 수치가 안정되도록 일부를 fp32로 바꾸고, 그래디언트 체크포인팅을 켭니다. 체크포인팅은 계산을 조금 더 하는 대신 메모리를 크게 아낍니다.

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

```text
VRAM: 1.50 GB
```

## 학습

LoRA 어댑터를 학습합니다.

### 14단계. LoRA 설정

원래 가중치 15억 개는 그대로 두고, 어텐션의 네 층(q, k, v, o projection)에 작은 행렬 두 개씩(LoRA 어댑터)을 붙여 그것만 학습합니다. 학습되는 숫자는 약 218만 개로 전체의 0.14%입니다.

| 설정 | 값 | 뜻 |
|---|---|---|
| `r` | 8 | 어댑터 행렬의 랭크. 클수록 표현력이 늘고 메모리도 늘어납니다 |
| `lora_alpha` | 16 | 어댑터 출력 배율은 alpha/r = 2 |
| `lora_dropout` | 0.05 | 과적합을 줄이는 드롭아웃 |
| `target_modules` | q, k, v, o | 어댑터를 붙일 층 |

자세한 원리는 로컬 폴더의 `QLoRA.md`에 정리돼 있습니다.

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

학습 방법을 정합니다. 주요 값은 다음과 같습니다.

| 설정 | 값 | 뜻 |
|---|---|---|
| `completion_only_loss` | True | 답변 토큰에만 손실을 겁니다 |
| `num_train_epochs` | 1 | 학습 데이터를 한 바퀴만 봅니다 |
| `per_device_train_batch_size` | 1 | 한 번에 샘플 1개씩 계산합니다 |
| `gradient_accumulation_steps` | 8 | 8개를 모아 한 번 갱신합니다. 실질 배치는 8, 500건이면 63번 갱신 |
| `learning_rate` | 2e-4 | 한 번 갱신할 때의 최대 보폭. 처음 3%는 워밍업, 이후 코사인으로 줄어듭니다 |
| `fp16` | True | Turing GPU라 bf16 대신 fp16 |
| `optim` | paged_adamw_8bit | 옵티마이저 상태를 8비트로 저장하는 AdamW |
| `eval_strategy` | epoch | 학습이 끝날 때 검증 손실을 계산합니다 |

배치 크기 1과 그래디언트 체크포인팅은 4GB GPU에 맞춘 값입니다. T4에서는 여유가 있지만, 로컬 결과와 비교할 수 있도록 같게 두었습니다.

```python
train_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    max_length=MAX_LENGTH,
    completion_only_loss=True,      # 답변 토큰에만 손실을 겁니다
    num_train_epochs=1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    gradient_checkpointing=True,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    fp16=True,                      # Turing 세대(T4, GTX 1650)라 bf16은 못 씁니다
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

학습을 시작합니다. 진행 막대와 함께 10스텝마다 학습 손실(Training Loss)이 표에 찍히고, 끝나면 검증 손실(Validation Loss)이 나옵니다.

로컬 GTX 1650에서는 학습에 약 55분, 검증에 약 4분 걸렸습니다. T4는 텐서 코어가 있어 더 빠를 것으로 예상하지만 재 보지는 않았습니다.

로컬 결과는 다음과 같았습니다. glaive 답변은 모델이 생성한 글이라 원래 Qwen에게 예측하기 쉬워서, 손실이 처음부터 낮고 크게 줄지 않습니다.

| 스텝 | 학습 손실 |
|---|---|
| 10 | 0.64 |
| 30 | 0.56 |
| 60 | 0.58 |
| 검증 | 0.56 |

Colab 무료 사용은 한동안 브라우저 탭을 조작하지 않으면 세션이 끊길 수 있습니다. 학습 중에는 탭을 열어 두세요.

```python
trainer.train()
```

예상 결과:

```text
TrainOutput(global_step=63, training_loss=0.57..., ...)
```

### 18단계. 최대 GPU 메모리 확인

학습 중 GPU 메모리를 가장 많이 썼을 때의 값입니다. 로컬에서는 2.58GB였습니다. T4의 16GB에는 여유가 많습니다.

```python
print("peak VRAM: %.2f GB" % (torch.cuda.max_memory_reserved() / 1024**3))
```

예상 결과:

```text
peak VRAM: 2.58 GB
```

## 결과 저장

학습 결과를 저장하고 내려받습니다.

### 19단계. 어댑터 저장

학습한 LoRA 어댑터를 `qwen-glaive-python` 폴더에 저장합니다. 원래 모델 전체가 아니라 어댑터(A, B 행렬)만 저장되므로 약 9MB입니다. 나중에 쓸 때는 원래 Qwen 모델을 받아 이 어댑터를 얹습니다.

```python
trainer.save_model(OUTPUT_DIR)
```

### 20단계. 결과 저장 (Colab 전용)

Colab의 파일은 세션이 끝나면 모두 사라집니다. 저장한 폴더를 zip으로 묶어 밖으로 빼냅니다. 확인 단계에서 세션이 끊겨도 결과를 잃지 않도록, 확인보다 먼저 저장합니다.

방법은 두 가지이고 `SAVE_TO_DRIVE`로 고릅니다.

**`False` (기본값): 내 PC로 내려받기.** 브라우저의 다운로드 창이 뜹니다. 브라우저가 다운로드를 막으면 허용해 주세요. 파일 탭(왼쪽 폴더 아이콘)에서 `qwen-glaive-python.zip`을 오른쪽 클릭해 내려받아도 됩니다.

**`True`: Google Drive에 저장.** 셀을 실행하면 Google 계정 접근을 허용하라는 창이 뜹니다. 계정을 고르고 허용하면 Drive가 `/content/drive`에 연결되고, zip이 **내 드라이브 > fine-tuning** 폴더에 복사됩니다. 폴더가 없으면 새로 만듭니다. 저장 위치를 바꾸려면 `DRIVE_DIR`을 고치세요.

Drive 저장이 편리한 경우는 세 가지입니다. 파일이 커서 내려받기가 오래 걸릴 때, 브라우저가 다운로드를 막을 때, 나중에 Colab에서 다시 쓸 때입니다.

Drive 무료 용량은 15GB이고 이 zip은 약 29MB입니다. 회사나 학교 계정은 관리자가 Colab의 Drive 연결을 막아 두었을 수 있습니다.

```python
import shutil

# False면 내 PC로 내려받고, True면 Google Drive에 저장합니다.
SAVE_TO_DRIVE = False
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
    print("로컬 환경이라 내려받기를 건너뜁니다. 결과는", OUTPUT_DIR, "폴더에 있습니다.")
```
예상 결과:


````text
SAVE_TO_DRIVE = False 일 때: 브라우저의 다운로드 창이 뜹니다.

SAVE_TO_DRIVE = True 일 때:
Mounted at /content/drive
Drive에 저장: /content/drive/MyDrive/fine-tuning/qwen-glaive-python.zip
````

**Drive에 저장한 결과를 다음에 쓰려면** 새 Colab 세션에서 내 PC에서 올릴 필요 없이 Drive에서 바로 풉니다. 추론 노트북(`glaive_infer.md` 4단계)에서 파일을 올리는 대신 아래 코드를 쓰면 됩니다.

```python
from google.colab import drive
drive.mount("/content/drive")
shutil.unpack_archive("/content/drive/MyDrive/fine-tuning/qwen-glaive-python.zip", "qwen-glaive-python")
```

## 확인

학습한 모델의 답을 원래 모델, 데이터셋의 답과 비교합니다.

### 21단계. 추론 준비

학습한 모델로 답을 만들기 전에 추론 상태로 바꿉니다.

- `eval()`: 학습 직후의 모델은 train 모드라 LoRA 드롭아웃이 켜져 있습니다. 그대로 생성하면 "Redis Ly下面是小下面是小..."처럼 출력이 무너집니다. 로컬에서 실제로 겪은 문제입니다.
- `gradient_checkpointing_disable()`: 체크포인팅이 켜져 있으면 KV 캐시가 꺼져 생성이 매우 느려집니다.
- `truncation_side = "left"`: 질문이 너무 길면 앞부분을 자릅니다. 뒤를 자르면 프롬프트 끝의 답변 시작 표시가 잘려 나갑니다.

**세션을 다시 시작했다면** 학습을 다시 하지 않아도 됩니다. 1~3단계, 데이터 준비(4~10단계), 4비트 양자화 설정(11단계)만 실행한 뒤 이 셀로 오세요. 메모리에 `trainer`가 없으면 저장된 어댑터를 불러옵니다. 단, 세션이 완전히 끊겨 파일이 사라졌다면 내려받은 zip을 파일 탭에 올리고 `qwen-glaive-python` 폴더에 풀어야 합니다.

```python
if "trainer" in globals():
    # 방금 학습한 모델을 그대로 씁니다
    tuned_model = trainer.model
    tuned_model.gradient_checkpointing_disable()
else:
    # 세션을 다시 시작했으면 저장된 어댑터를 불러옵니다
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

샘플 하나를 받아 모델의 답을 만드는 함수입니다. 학습 때와 같은 프롬프트를 만들고, 최대 200토큰까지 생성합니다. `do_sample=False`라 매번 같은 답이 나옵니다.

생성할 때 "The following generation flags are not valid" 경고가 나올 수 있는데, 모델 기본 설정의 샘플링 값이 무시된다는 뜻이라 무시해도 됩니다.

```python
def answer_for(item, max_new_tokens=200):
    prompt = messages_for(item)["prompt"]
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

### 23단계. 검증 질문 보기

학습에 쓰지 않은 검증 질문을 봅니다.

```python
print(val_set[0]["question"])
```

예상 결과:

```text
How can I create a list in Python that stores the first 10 numbers divisible by 4?
```

### 24단계. 파인튜닝한 모델의 답

학습한 모델의 답입니다. 로컬에서는 glaive 데이터처럼 코드와 설명을 길게 붙이는 문체로 바뀌었지만, 코드가 0, 4, 8만 만들어 답이 틀렸습니다.

```python
print(answer_for(val_set[0]))
```

### 25단계. 데이터셋의 답

데이터셋에 들어 있는 답입니다. glaive 답변은 모델이 생성한 것이라 정답이라는 보장이 없습니다. 이 질문의 데이터셋 답도 4와 8만 만들어 틀렸습니다.

```python
print(val_set[0]["answer"])
```

### 26단계. 원래 Qwen의 답

`disable_adapter()` 안에서는 어댑터가 꺼져 원래 Qwen이 됩니다. 모델을 다시 올리지 않고도 학습 전과 비교할 수 있습니다. 로컬에서는 원래 Qwen만 4부터 40까지 올바르게 답했습니다.

```python
with tuned_model.disable_adapter():
    print(answer_for(val_set[0]))
```

## 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 2단계에서 "라이브러리 버전이 다릅니다" | 설치 전에 불러온 예전 버전이 메모리에 남아 있음 | **런타임 > 세션 다시 시작** 후 2단계부터 다시 실행 |
| 3단계에서 "GPU가 없습니다" | 런타임이 CPU로 되어 있음 | **런타임 > 런타임 유형 변경**에서 T4 GPU 선택 후 1단계부터 다시 실행 |
| 1단계에서 빨간 "dependency conflicts" 경고 | Colab의 다른 패키지가 최신 버전을 원함 | 무시해도 됩니다 |
| "HF_TOKEN 시크릿이 없다"는 경고 | Hugging Face 로그인을 안 함 | 무시해도 됩니다. 공개 저장소라 그대로 받아집니다 |
| bitsandbytes 관련 오류 | Colab의 CUDA 버전과 bitsandbytes 0.47.0이 맞지 않을 수 있음 (확인하지 못한 부분) | 1단계 목록에서 `"bitsandbytes==0.47.0"`을 `"bitsandbytes"`로 바꿔 최신으로 설치 |
| 답변이 "下面是小下面是小..."처럼 무너짐 | 추론 준비(21단계)를 건너뜀 | 21단계를 실행한 뒤 다시 생성 |
| 학습 도중 세션이 끊김 | Colab 무료 사용의 유휴 시간 제한 | 학습 중에는 탭을 열어 두기. 끊기면 1단계부터 다시 |

## 결과를 로컬에서 쓰기

20단계에서 내려받은 `qwen-glaive-python.zip`을 로컬 WSL의 `/home/salee/fine-tuning` 폴더로 옮긴 뒤 폴더에 풉니다. **기존 로컬 학습 결과를 덮어쓰므로**, 남겨 두려면 먼저 폴더 이름을 바꾸세요.

```bash
cd /home/salee/fine-tuning
mv qwen-glaive-python qwen-glaive-python-local   # 로컬 결과를 남겨 두려면
unzip -o qwen-glaive-python.zip -d qwen-glaive-python
```

그다음 `fine_tun_local_infer.ipynb`에서 `ADAPTER_DIR = "qwen-glaive-python"` 줄의 주석을 풀고 실행하면, Gradio 화면에서 원래 Qwen과 비교할 수 있습니다.
