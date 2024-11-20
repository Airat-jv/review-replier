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

# Функция для получения списка маркетплейсов и кабинетов пользователя
async def get_user_marketplace_accounts(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_user_marketplace_accounts", params={
            'telegram_id': telegram_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('accounts', [])
            else:
                return []

# Функция для отправки выбора маркетплейса
async def send_marketplace_selection(chat_id):
    accounts = await get_user_marketplace_accounts(chat_id)
    if not accounts:
        await bot.send_message(chat_id, "У вас нет доступных кабинетов. Пожалуйста, добавьте кабинеты через команду /start.")
        return

    # Группируем кабинеты по маркетплейсам
    marketplaces = {}
    for account in accounts:
        mp = account['marketplace']
        if mp not in marketplaces:
            marketplaces[mp] = []
        marketplaces[mp].append(account)

    keyboard = InlineKeyboardMarkup(row_width=1)
    for mp, accs in marketplaces.items():
        if len(accs) == 1:
            # Если один кабинет, добавляем кнопку сразу для него
            callback_data = f"select_account:{accs[0]['id']}"
            button = InlineKeyboardButton(text=f"{mp} - {accs[0]['account_name']}", callback_data=callback_data)
            keyboard.add(button)
        else:
            # Если несколько кабинетов, добавляем кнопку для выбора кабинета
            callback_data = f"choose_account:{mp}"
            button = InlineKeyboardButton(text=f"{mp}", callback_data=callback_data)
            keyboard.add(button)
    await delete_previous_bot_message(chat_id)
    sent_message = await bot.send_message(chat_id, "Пожалуйста, выберите маркетплейс или кабинет:", reply_markup=keyboard)
    await storage.update_data(user=chat_id, data={'last_bot_message_id': sent_message.message_id})

# Функция для Обработать выбор кабинета
@dp.callback_query_handler(lambda c: c.data.startswith('choose_account:'))
async def process_choose_account(callback_query: types.CallbackQuery):
    marketplace = callback_query.data.split(':')[1]
    accounts = await get_user_marketplace_accounts(callback_query.from_user.id)
    accounts = [acc for acc in accounts if acc['marketplace'] == marketplace]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for acc in accounts:
        callback_data = f"select_account:{acc['id']}"
        button = InlineKeyboardButton(text=acc['account_name'], callback_data=callback_data)
        keyboard.add(button)
    await delete_previous_bot_message(callback_query.from_user.id)
    sent_message = await bot.send_message(callback_query.from_user.id, "Выберите кабинет:", reply_markup=keyboard)
    await storage.update_data(user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})
    await callback_query.answer()

# Функция для Обработать выбор аккаунта
@dp.callback_query_handler(lambda c: c.data.startswith('select_account:'))
async def process_select_account(callback_query: types.CallbackQuery):
    account_id = int(callback_query.data.split(':')[1])
    # Сохраняем выбранный аккаунт
    await storage.update_data(user=callback_query.from_user.id, data={'selected_account_id': account_id})
    # Получаем информацию об аккаунте (например, для получения иконки)
    # ...
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = "Получить свежий отзыв"
    keyboard.add(button_text)
    await delete_previous_bot_message(callback_query.from_user.id)
    sent_message = await bot.send_message(
        chat_id=callback_query.from_user.id,
        text="Вы выбрали кабинет.",
        reply_markup=keyboard
    )
    await storage.update_data(user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})
    await callback_query.answer()

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
            InlineKeyboardButton("Управление кабинетами", url=f"{EXTERNAL_BACKEND_URL}/add_marketplace?token={auth_token}"),
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
@dp.message_handler(lambda message: message.text == "Получить свежий отзыв")
async def get_fresh_review(message: types.Message):
    user_data = await storage.get_data(user=message.from_user.id)
    account_id = user_data.get('selected_account_id')
    if not account_id:
        await message.answer("Сначала выберите кабинет. Нажмите /start для выбора.")
        return
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_review", params={
            'telegram_id': message.from_user.id,
            'account_id': account_id
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                review = data.get('review')
                await message.answer(f"Свежий отзыв:\n\n{review}")
            else:
                await message.answer("Не удалось получить отзыв. Пожалуйста, попробуйте позже.")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=set_default_commands)
