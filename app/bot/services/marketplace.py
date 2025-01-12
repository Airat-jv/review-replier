# Логика получения отзывов с Я.Маркета
# app/bot/services/marketplace.py

import os
import aiohttp

# Этот URL для обращения к вашему бэкенду или напрямую к API Маркета
BACKEND_URL = os.getenv('BACKEND_URL', 'http://backend:8000')

async def get_user_marketplace_accounts(telegram_id: int) -> list:
    """
    Получает список кабинетов (marketplace accounts) для пользователя с given telegram_id.
    Здесь, как пример, вызываем эндпоинт вашего backend, который возвращает данные 
    в формате {'accounts': [...]}. 
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BACKEND_URL}/get_user_marketplace_accounts",
            params={"telegram_id": telegram_id},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Предположим, что в data = {"accounts": [...]}
                return data.get("accounts", [])
            else:
                return []