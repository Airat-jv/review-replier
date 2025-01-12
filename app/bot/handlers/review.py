# app/bot/handlers/review.py

import aiohttp
import os
from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, ParseMode
from app.bot.bot import dp, storage
from app.bot.services.replies import send_user_reply
from app.bot.services.ui import send_main_menu

BACKEND_URL = os.getenv('BACKEND_URL', 'http://backend:8000')

@dp.message_handler(lambda message: message.text in ["Получить отзыв", "Перейти к следующему"])
async def handle_review_actions(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    loading_message = await message.answer("🤖Получаем данные… \n✨Генерируем ответ… ")

    account_id = user_data.get('selected_account_id')
    if not account_id:
        await message.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await message.answer("Сначала выберите кабинет. Нажмите /start для выбора.")
        return

    page_token = None
    if "Перейти к следующему" in message.text:
        page_token = user_data.get('next_page_token')

    params = {'telegram_id': user_id, 'account_id': account_id}
    if page_token:
        params['page_token'] = page_token

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_review", params=params) as resp:
            await message.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)

            if resp.status == 200:
                data = await resp.json()
                review = data.get('review')
                reply = data.get('reply')
                review_id = data.get('review_id')
                new_next_page_token = data.get('next_page_token')

                if review_id:
                    user_data['review'] = review
                    user_data['suggested_reply'] = reply
                    user_data['review_id'] = review_id
                    user_data['next_page_token'] = new_next_page_token
                    user_data['current_mode'] = None
                    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

                    await message.answer(f"**Отзыв:**\n\n{review}", parse_mode=ParseMode.MARKDOWN)
                    await message.answer(f"**Предлагаемый ответ:**\n\n{reply}", parse_mode=ParseMode.MARKDOWN)

                    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                    keyboard.add("Отправить предложенный ответ", "Написать свой ответ")
                    keyboard.add("Перейти к следующему")
                    await message.answer("Выберите действие:", reply_markup=keyboard)
                else:
                    await message.answer("Больше нет отзывов.")
                    user_data['current_mode'] = None
                    await storage.update_data(chat=chat_id, user=user_id, data=user_data)
                    await send_main_menu(user_id, user_data.get('marketplace'))
            else:
                await message.answer("Не удалось получить отзыв. Пожалуйста, попробуйте позже.")

@dp.message_handler(lambda message: message.text in ["Отправить предложенный ответ", "Написать свой ответ"])
async def handle_reply_choice(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    if message.text == "Отправить предложенный ответ":
        suggested_reply = user_data.get('suggested_reply')
        if suggested_reply is None:
            await message.answer("Предложенный ответ не найден. Попробуйте снова получить отзыв.")
            return

        success = await send_user_reply(message, suggested_reply)
        if success:
            await message.answer("Ответ успешно отправлен на Яндекс.Маркет.")
        else:
            await message.answer("Не удалось отправить ответ. Пожалуйста, попробуйте позже.")

        user_data['current_mode'] = None
        await storage.update_data(chat=chat_id, user=user_id, data=user_data)
        await send_main_menu(user_id, user_data.get('marketplace'))

    elif message.text == "Написать свой ответ":
        user_data['current_mode'] = 'waiting_for_custom_reply'
        await storage.update_data(chat=chat_id, user=user_id, data=user_data)
        await message.answer("Пожалуйста, напишите ваш ответ на отзыв.")

@dp.message_handler(lambda message: message.text in ["Да, отправить", "Нет, изменить"])
async def process_confirmation(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    if user_data.get('current_mode') == 'confirming_reply':
        if message.text == "Да, отправить":
            custom_reply = user_data.get('custom_reply')
            success = await send_user_reply(message, custom_reply)
            if success:
                await message.answer("Ответ успешно отправлен на Яндекс.Маркет.")
            else:
                await message.answer("Не удалось отправить ответ. Пожалуйста, попробуйте позже.")

            user_data['current_mode'] = None
            await storage.update_data(chat=chat_id, user=user_id, data=user_data)
            await send_main_menu(user_id, user_data.get('marketplace'))

        elif message.text == "Нет, изменить":
            user_data['current_mode'] = 'waiting_for_custom_reply'
            await storage.update_data(chat=chat_id, user=user_id, data=user_data)
            await message.answer("Пожалуйста, напишите ваш ответ на отзыв.")
    else:
        await message.answer("Сейчас не ожидается подтверждение. Попробуйте снова.")

@dp.message_handler(lambda message: True)
async def process_custom_reply(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    if user_data.get('current_mode') == 'waiting_for_custom_reply':
        custom_reply = message.text
        user_data['custom_reply'] = custom_reply
        user_data['current_mode'] = 'confirming_reply'
        await storage.update_data(chat=chat_id, user=user_id, data=user_data)

        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("Да, отправить", "Нет, изменить")

        await message.answer(f"Вы уверены, что хотите отправить этот ответ?\n\n{custom_reply}", reply_markup=keyboard)
    else:
        await message.answer("Сейчас не ожидается пользовательский ответ.")