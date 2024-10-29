from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

import os
import requests

# Получаем OAuth токен из переменной окружения
ACCESS_TOKEN = os.getenv("API_KEY")

if ACCESS_TOKEN is None:
    raise ValueError("ACCESS_TOKEN is not set. Please set the API_KEY environment variable.")

# Формирование URL для получения отзывов
business_id = 3999348
URL = f"https://api.partner.market.yandex.ru/v2/businesses/{business_id}/goods-feedback"

# Заголовки для авторизации
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Параметры запроса - лимит количества отзывов
params = {
    "limit": 1
}

# Тело запроса
data = {
    "reactionStatus": "NEED_REACTION",
    "paid": False
}

# Выполнение POST запроса для получения одного последнего отзыва
response = requests.post(URL, headers=headers, params=params, json=data)

# Обработка ответа
if response.status_code == 200:
    result = response.json()
    feedbacks = result.get("result", {}).get("feedbacks", [])
    if feedbacks:
        feedback = feedbacks[0]  # Получаем только один последний отзыв
        print(feedback)  # Выводим последний отзыв
    else:
        print("Нет отзывов, требующих ответа.")
else:
    print(f"Ошибка при получении отзывов: {response.status_code}, {response.text}")
