from fastapi import FastAPI
import os
import requests

app = FastAPI()

ACCESS_TOKEN = os.getenv("API_KEY")

if ACCESS_TOKEN is None:
    raise ValueError("ACCESS_TOKEN is not set. Please set the API_KEY environment variable.")

business_id = 3999348
URL = f"https://api.partner.market.yandex.ru/v2/businesses/{business_id}/goods-feedback"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

params = {
    "limit": 1
}

data = {
    "reactionStatus": "NEED_REACTION",
    "paid": False
}

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.get("/feedback")
async def get_feedback():
    response = requests.post(URL, headers=headers, params=params, json=data)
    response.encoding = 'utf-8'  # Устанавливаем кодировку

    if response.status_code == 200:
        result = response.json()
        feedbacks = result.get("result", {}).get("feedbacks", [])
        if feedbacks:
            feedback = feedbacks[0]
            return feedback
        else:
            return {"message": "Нет отзывов, требующих ответа."}
    else:
        return {
            "error": f"Ошибка при получении отзывов: {response.status_code}",
            "details": response.text
        }
