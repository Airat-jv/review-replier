# Логика отправки ответов
# для send_user_reply
# app/bot/services/replies.py

import aiohttp
import os
from app.bot.bot import storage

BACKEND_URL = os.getenv('BACKEND_URL', 'http://backend:8000')

async def send_user_reply(message, custom_reply: str) -> bool:
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    account_id = user_data.get('selected_account_id')
    review_id = user_data.get('review_id')

    if not account_id or not review_id:
        return False

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/send_reply", json={
            'telegram_id': user_id,
            'account_id': account_id,
            'review_id': review_id,
            'reply': custom_reply
        }) as resp:
            return resp.status == 200