from openai import OpenAI
import os
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.responses.create(
    model="gpt-5-mini",
    input="请用一句话解释什么是套利。",
    reasoning={
        "effort": "medium"   # 关闭推理
    }
)

print(response)