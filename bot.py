# bot.py

import os
import aiohttp
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Получаем переменные окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://backend:8000')
EXTERNAL_BACKEND_URL = os.getenv('EXTERNAL_BACKEND_URL')
BOT_USERNAME = os.getenv('BOT_USERNAME')

if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить переменную окружения TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Установка команд бота
async def set_default_commands(dp):
    await bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Помощь")
    ])

# Функция для проверки авторизации пользователя
async def check_authorization(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/is_authorized", params={
            'telegram_id': telegram_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('authorized', False)
            else:
                return False

# Функция для получения информации о пользователе
async def get_user_info(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/user_info", params={
            'telegram_id': telegram_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                return {}

# Функция для генерации токена
async def generate_token(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/generate_token", json={
            'telegram_id': telegram_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('token')
            else:
                return ''

# Функция для получения списка маркетплейсов пользователя
async def get_user_marketplaces(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_user_marketplaces", params={
            'telegram_id': telegram_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('marketplaces', [])
            else:
                return []

# Функция для отправки выбора маркетплейса
async def send_marketplace_selection(chat_id):
    marketplaces = await get_user_marketplaces(chat_id)
    if not marketplaces:
        await bot.send_message(chat_id, "У вас нет доступных маркетплейсов. Пожалуйста, добавьте маркетплейсы через команду /start.")
        return
    keyboard = InlineKeyboardMarkup(row_width=1)
    for marketplace in marketplaces:
        button = InlineKeyboardButton(text=marketplace, callback_data=f"select_marketplace:{marketplace}")
        keyboard.add(button)
    # Удаляем предыдущее сообщение
    await delete_previous_bot_message(chat_id)
    # Отправляем новое сообщение
    sent_message = await bot.send_message(chat_id, "Пожалуйста, выберите маркетплейс:", reply_markup=keyboard)
    # Сохраняем message_id
    await storage.update_data(user=chat_id, data={'last_bot_message_id': sent_message.message_id})

# Функция для удаления предыдущего сообщения бота
async def delete_previous_bot_message(chat_id):
    user_data = await storage.get_data(user=chat_id)
    last_message_id = user_data.get('last_bot_message_id')
    if last_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        except:
            pass  # Если сообщение уже удалено или недоступно

# Функция для получения иконки маркетплейса
def get_marketplace_icon(marketplace):
    icons = {
        'Яндекс.Маркет': '🟡',
        'OZON': '🔵',
        'Wildberries': '🟣'
    }
    return icons.get(marketplace, '')

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    is_authorized = await check_authorization(message.from_user.id)
    await delete_previous_bot_message(message.chat.id)  # Удаляем предыдущее сообщение
    if is_authorized:
        user_info = await get_user_info(message.from_user.id)
        name = user_info.get('name', '')
        auth_token = user_info.get('auth_token', '')
        if not auth_token:
            auth_token = await generate_token(message.from_user.id)
        greeting = f"Здравствуйте, {name}! Добро пожаловать в *ReviewReplierBot*!\n\n"
        welcome_text = (
            f"{greeting}"
            "Этот бот поможет вам управлять отзывами на маркетплейсах. Вы можете получать свежие отзывы и быстро отвечать на них с помощью интеграции с ChatGPT.\n\n"
            "Выберите нужное действие ниже:"
        )
        keyboard = InlineKeyboardMarkup(row_width=1)
        buttons = [
            InlineKeyboardButton("Выбрать маркетплейс", callback_data="choose_marketplace"),
            InlineKeyboardButton("Добавить маркетплейс", url=f"{EXTERNAL_BACKEND_URL}/auth?token={auth_token}&action=add_marketplace"),
            InlineKeyboardButton("Помощь", callback_data="help")
        ]
        keyboard.add(*buttons)
        # Отправляем изображение с сообщением
        with open('welcome_image.jpg', 'rb') as photo:
            sent_message = await message.answer_photo(
                photo,
                caption=welcome_text,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        # Сохраняем message_id
        await storage.update_data(user=message.from_user.id, data={'last_bot_message_id': sent_message.message_id})
    else:
        token = await generate_token(message.from_user.id)
        keyboard = InlineKeyboardMarkup(row_width=1)
        buttons = [
            InlineKeyboardButton("Авторизоваться", url=f"{EXTERNAL_BACKEND_URL}/auth?token={token}"),
            InlineKeyboardButton("Помощь", callback_data="help")
        ]
        keyboard.add(*buttons)
        sent_message = await message.answer(
            "Здравствуйте! Пожалуйста, авторизуйтесь, чтобы начать работу.",
            reply_markup=keyboard
        )
        # Сохраняем message_id
        await storage.update_data(user=message.from_user.id, data={'last_bot_message_id': sent_message.message_id})

# Обработчик команды /help
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await delete_previous_bot_message(message.chat.id)  # Удаляем предыдущее сообщение
    help_text = (
        "ℹ️ *Популярные вопросы:*\n\n"
        "🔹 *Как авторизоваться?*\n"
        "— Нажмите кнопку 'Авторизоваться' и следуйте инструкциям.\n\n"
        "🔹 *Как добавить маркетплейс?*\n"
        "— Нажмите кнопку 'Добавить маркетплейс' и следуйте инструкциям.\n\n"
        "🔹 *Как получить свежий отзыв?*\n"
        "— Выберите маркетплейс и нажмите кнопку 'Получить свежий отзыв'.\n\n"
        "Если у вас есть дополнительные вопросы, обратитесь к администратору."
    )
    sent_message = await message.answer(help_text, parse_mode=types.ParseMode.MARKDOWN)
    # Сохраняем message_id
    await storage.update_data(user=message.from_user.id, data={'last_bot_message_id': sent_message.message_id})

# Обработчик нажатия на инлайн-кнопки
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    if data == 'choose_marketplace':
        await send_marketplace_selection(callback_query.from_user.id)
    elif data == 'help':
        await cmd_help(callback_query.message)
    elif data.startswith('select_marketplace:'):
        marketplace = data.split(':')[1]
        await process_marketplace_selection(callback_query, marketplace)
    await callback_query.answer()

# Обработчик выбора маркетплейса
async def process_marketplace_selection(callback_query: types.CallbackQuery, marketplace: str):
    # Сохраняем выбранный маркетплейс
    await storage.update_data(user=callback_query.from_user.id, data={'selected_marketplace': marketplace})
    # Создаём обычную клавиатуру с кнопкой "Получить свежий отзыв"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = f"Получить свежий отзыв {get_marketplace_icon(marketplace)}"
    keyboard.add(button_text)
    # Удаляем предыдущее сообщение
    await delete_previous_bot_message(callback_query.from_user.id)
    # Отправляем новое сообщение с клавиатурой
    sent_message = await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=f"Вы выбрали: {marketplace}",
        reply_markup=keyboard
    )
    # Сохраняем message_id
    await storage.update_data(user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})

# Обработчик кнопки "Получить свежий отзыв"
@dp.message_handler(lambda message: message.text.startswith("Получить свежий отзыв"))
async def get_fresh_review(message: types.Message):
    user_data = await storage.get_data(user=message.from_user.id)
    marketplace = user_data.get('selected_marketplace')
    if not marketplace:
        await message.answer("Сначала выберите маркетплейс. Нажмите /start для выбора.")
        return
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_review", params={
            'telegram_id': message.from_user.id,
            'marketplace': marketplace
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                review = data.get('review')
                # Не удаляем сообщение с отзывом
                await message.answer(f"Свежий отзыв с {marketplace}:\n\n{review}")
            else:
                await message.answer("Не удалось получить отзыв. Пожалуйста, попробуйте позже.")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=set_default_commands)
