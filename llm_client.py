import os

from openai import OpenAI

def call_llm(prompt):
    """发送 prompt 给 DeepSeek返回模型回答文本。"""

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("请先设置 DEEPSEEK_API_KEY 环境变量")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=120.0,
        max_retries=1,
    )

    response = client.chat.completions.create(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=10000,
        stream=False,
    )

    if response.choices[0].finish_reason == "length":
        raise RuntimeError("模型回答被截断，请增加 max_tokens")

    answer = response.choices[0].message.content
    if not answer or not answer.strip():
        raise RuntimeError("模型返回了空回答")

    return answer.strip()
