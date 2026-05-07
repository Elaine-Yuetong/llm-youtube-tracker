from openai import OpenAI

client = OpenAI(
    api_key="sk-hdQYopuKAsKHYEFNA0F66e140c2a48909bEf7f625fB4Bf4a",
    base_url="https://api.apiyi.com/v1"
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "说一句你好"}]
)

print(response.choices[0].message.content)