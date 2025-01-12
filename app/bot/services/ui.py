# для send_main_menu
# app/bot/services/ui.py

from aiogram.types import ReplyKeyboardMarkup
from app.bot.bot import bot

async def send_main_menu(user_id: int, marketplace: str):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = "Получить отзыв"
    keyboard.add(button_text)
    await bot.send_message(
        chat_id=user_id,
        text="Вы можете выбрать действие:",
        reply_markup=keyboard
    )