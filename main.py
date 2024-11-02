from fastapi import FastAPI, Response
import os
import requests
import json

app = FastAPI()

@app.get("/feedback")
def get_feedback():
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

    response = requests.post(URL, headers=headers, params=params, json=data)

    if response.status_code == 200:
        feedback_data = response.json()
        json_response = json.dumps(feedback_data, ensure_ascii=False)
        return Response(content=json_response, media_type="application/json; charset=utf-8")
    else:
        return {"error": f"Ошибка при получении отзывов: {response.status_code}, {response.text}"}
