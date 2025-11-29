import os
from dotenv import load_dotenv # 패키지 불러오기
from transformers import AutoTokenizer, AutoModelForCausalLM

# 1. .env 파일 로드 (이 코드가 실행되면 환경변수가 메모리에 올라감)
load_dotenv()

# 2. 가져오기
hf_token = os.getenv("HF_TOKEN")

model_id = "Qwen/Qwen2.5-0.5B-Instruct"

print(f"Downloading {model_id}...")

# 3. 토큰 사용 (token= 파라미터에 넣기)
# Qwen은 필요 없지만, Llama-3 같은 거 쓸 땐 이렇게 넣으면 됩니다.
tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)
model = AutoModelForCausalLM.from_pretrained(model_id, token=hf_token)

print("✅ Model loaded successfully!")