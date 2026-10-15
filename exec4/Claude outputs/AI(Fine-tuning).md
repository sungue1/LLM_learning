# AI(Fine-tuning) (10/14) _31일차

## 🖥️ LLM

### 용어 정리

- **fine-tuning**: 이미 훈련된 대규모 언어 모델(LLM)에 특정 데이터셋을 추가로 학습시켜, 모델을 특정 작업이나 도메인에 맞게 조정하는 과정
- **LoRA**: PEFT 방법 중 하나로, PLM의 기본 가중치는 고정 상태로 유지하면서, 학습이 가능한 저차원의 가중치 행렬을 추가하여 모델을 조정
  - **r(어댑터의 크기)**: 행렬의 폭으로 주로 8~16 사이의 값을 가짐
  - **alpha(어댑터 출력의 배율)**: r에 곱하는 값으로 어댑터의 영향력을 조정
  - **learning rate(학습률)**: 가중치를 고칠 때의 수정 정도
- **QLoRA**: LoRA의 확장된 형태로, LoRA 기법에 새로운 형태의 양자화를 적용하여 메모리 사용과 계산량을 더욱 줄이는 방법. 2^16개였던 표현 값을 2^4로 줄이고 대표 값을 정규분포에 맞춰서 성능은 유지하고 메모리 사용을 감소
- **파라미터**: 데이터로부터 결정되는 모델 내부의 매개변수
- **하이퍼파라미터**: 최적의 훈련 모델을 구현하기 위해 사용자가 직접 모델에 설정하는 변수
- **langGraph**:
- **langchain**:

### Fine-tuning 진행 순서

목표·베이스라인 설정 → 데이터 수집·정제 → 포맷 변환(JSONL) → 데이터 분할(학습·검증·테스트) → 모델·학습 방법 선정(모델 및 하이퍼파라미터) → 학습 → 평가 → 개선(반복) → 배포

- 데이터셋을 학습(Train), 검증(Validation), 테스트(Test)로 각각 **7:1:2** 정도의 비율로 구성 후 사용

### 실습 파일 정리

- **glaive_colab.md**: 영어 python 코딩 질문을 학습
- **koalpaca_colab.md**: 한국어 네이버 지식인 질문을 학습
- **glaive_infer_colab.md**: 학습한 어댑터로 기존의 Qwen(fine-tuning 전)와 비교

## 출처 및 참고 사이트

- https://doug.tistory.com/44
- https://ittrue.tistory.com/42
- https://bkshin.tistory.com/entry/머신러닝-13-파라미터Parameter와-하이퍼-파라미터Hyper-parameter
- https://vessl.ai/ko/blog/fine-tuning-definition-examples-methods
