
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_news(title, url):
    prompt = f"""Ты спортивный редактор. Напиши краткую, интересную аннотацию к новости по заголовку:
Заголовок: {title}
Ссылка: {url}
Ответ (1-2 предложения):"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    return response['choices'][0]['message']['content'].strip()
