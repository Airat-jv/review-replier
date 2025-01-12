# Логика бота
# app/bot/bot.py

import os
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить переменную окружения TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Импортируем хэндлеры, чтобы они зарегистрировались в dp
from app.bot.handlers import user, review

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)