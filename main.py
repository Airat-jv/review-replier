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

# Начальное значение для page_token
page_token = None

# Получение отзывов с обработкой пагинации
while True:
    # Параметры запроса - лимит количества отзывов и page_token
    params = {
        "limit": 1
    }
    if page_token:
        params["page_token"] = page_token

    # Тело запроса
    data = {
        "reactionStatus": "NEED_REACTION",
        "paid": False
    }

    # Выполнение POST запроса
    response = requests.post(URL, headers=headers, params=params, json=data)

    # Обработка ответа
    if response.status_code == 200:
        result = response.json()
        feedbacks = result.get("result", {}).get("feedbacks", [])
        for feedback in feedbacks:
            print(feedback)  # Выводим каждый отзыв

        # Получаем токен следующей страницы
        page_token = result.get("result", {}).get("paging", {}).get("nextPageToken")
        if not page_token:
            break  # Если токена следующей страницы нет, прекращаем цикл

    else:
        print(f"Ошибка при получении отзывов: {response.status_code}, {response.text}")
        break
