# app/bot/handlers/user.py
print("Loading user.py...", flush=True)
import aiohttp
import os
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from app.bot.bot import dp, bot, storage
from app.bot.services.marketplace import get_user_marketplace_accounts
from app.bot.services.ui import send_main_menu

BACKEND_URL = os.getenv('BACKEND_URL', 'http://backend:8000')
EXTERNAL_BACKEND_URL = os.getenv('EXTERNAL_BACKEND_URL')

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

async def delete_previous_bot_message(chat_id, user_id):
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    last_message_id = user_data.get('last_bot_message_id')
    if last_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        except:
            pass

async def send_marketplace_selection(chat_id):
    accounts = await get_user_marketplace_accounts(chat_id)
    if not accounts:
        await bot.send_message(chat_id, "У вас нет доступных кабинетов. Пожалуйста, добавьте кабинеты через команду /start.")
        return

    marketplaces = {}
    for account in accounts:
        mp = account['marketplace']
        if mp not in marketplaces:
            marketplaces[mp] = []
        marketplaces[mp].append(account)

    keyboard = InlineKeyboardMarkup(row_width=1)
    for mp, accs in marketplaces.items():
        if len(accs) == 1:
            callback_data = f"select_account:{accs[0]['id']}"
            button = InlineKeyboardButton(text=f"{mp} - {accs[0]['account_name']}", callback_data=callback_data)
            keyboard.add(button)
        else:
            callback_data = f"choose_account:{mp}"
            button = InlineKeyboardButton(text=f"{mp}", callback_data=callback_data)
            keyboard.add(button)

    await delete_previous_bot_message(chat_id, chat_id)
    sent_message = await bot.send_message(chat_id, "Пожалуйста, выберите маркетплейс или кабинет:", reply_markup=keyboard)
    await storage.update_data(chat=chat_id, user=chat_id, data={'last_bot_message_id': sent_message.message_id})

import logging
logging.basicConfig(level=logging.DEBUG)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    logging.info("Handler /start triggered!!!")
    await message.answer("Привет! Это тестовая реакция на /start.")
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    user_data.clear()
    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

    is_authorized = await check_authorization(user_id)
    await delete_previous_bot_message(chat_id, user_id)
    if is_authorized:
        await message.answer("Пожалуйста, выберите маркетплейс:", reply_markup=ReplyKeyboardRemove())
        user_info = await get_user_info(user_id)
        name = user_info.get('name', '')
        auth_token = user_info.get('auth_token', '')
        if not auth_token:
            auth_token = await generate_token(user_id)
        greeting = f"Здравствуйте, {name}! Добро пожаловать в *ReviewReplierBot*!\n\n"
        welcome_text = (
            f"{greeting}"
            "Этот бот поможет вам управлять отзывами. Вы можете получать отзывы и отвечать на них.\n\n"
            "Выберите нужное действие ниже:"
        )
        keyboard = InlineKeyboardMarkup(row_width=1)
        buttons = [
            InlineKeyboardButton("Выбрать маркетплейс", callback_data="choose_marketplace"),
            InlineKeyboardButton("Управление кабинетами", url=f"{EXTERNAL_BACKEND_URL}/add_marketplace?token={auth_token}"),
            InlineKeyboardButton("Помощь", callback_data="help")
        ]
        keyboard.add(*buttons)
        with open('welcome_image.jpg', 'rb') as photo:
            sent_message = await message.answer_photo(
                photo,
                caption=welcome_text,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        await storage.update_data(chat=chat_id, user=user_id, data={'last_bot_message_id': sent_message.message_id})
    else:
        token = await generate_token(user_id)
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
        await storage.update_data(chat=chat_id, user=user_id, data={'last_bot_message_id': sent_message.message_id})

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    await delete_previous_bot_message(chat_id, user_id)

    help_text = (
        "ℹ️ *Популярные вопросы:*\n\n"
        "🔹 *Как авторизоваться?*\n"
        "— Нажмите кнопку 'Авторизоваться' и следуйте инструкциям.\n\n"
        "🔹 *Как добавить маркетплейс?*\n"
        "— Нажмите кнопку 'Добавить маркетплейс' и следуйте инструкциям.\n\n"
        "🔹 *Как получить отзыв?*\n"
        "— Выберите маркетплейс и нажмите кнопку 'Получить отзыв'.\n\n"
        "Если есть вопросы, обратитесь к администратору."
    )
    sent_message = await message.answer(help_text, parse_mode=types.ParseMode.MARKDOWN)
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    user_data['last_bot_message_id'] = sent_message.message_id
    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if data == 'choose_marketplace':
        await send_marketplace_selection(user_id)
    elif data == 'help':
        await cmd_help(callback_query.message)
    elif data.startswith('choose_account:'):
        # Логика выбора аккаунта
        accounts = await get_user_marketplace_accounts(user_id)
        marketplace = data.split(':')[1]
        accounts = [acc for acc in accounts if acc['marketplace'] == marketplace]

        if accounts:
            keyboard = InlineKeyboardMarkup(row_width=1)
            for acc in accounts:
                callback_data = f"select_account:{acc['id']}"
                button = InlineKeyboardButton(text=acc['account_name'], callback_data=callback_data)
                keyboard.add(button)
            await delete_previous_bot_message(user_id, user_id)
            sent_message = await bot.send_message(user_id, "Выберите кабинет:", reply_markup=keyboard)
            await storage.update_data(chat=user_id, user=user_id, data={'last_bot_message_id': sent_message.message_id})
        else:
            await bot.send_message(user_id, "У вас нет кабинетов на выбранном маркетплейсе.")
        await callback_query.answer()
    elif data.startswith('select_account:'):
        account_id = int(data.split(':')[1])
        accounts = await get_user_marketplace_accounts(user_id)
        account_info = next((acc for acc in accounts if acc['id'] == account_id), None)
        if account_info is None:
            await bot.send_message(user_id, "Не удалось получить информацию о выбранном кабинете.")
            return

        marketplace = account_info.get('marketplace')
        user_data = await storage.get_data(chat=user_id, user=user_id)
        user_data['selected_account_id'] = account_id
        user_data['marketplace'] = marketplace
        user_data['next_page_token'] = None
        await storage.update_data(chat=user_id, user=user_id, data=user_data)

        await delete_previous_bot_message(user_id, user_id)
        account_name = account_info.get('account_name')
        await bot.send_message(
            chat_id=user_id,
            text=f"Вы выбрали кабинет *{account_name}* на *{marketplace}*.",
            parse_mode=types.ParseMode.MARKDOWN
        )

        await send_main_menu(user_id, marketplace)
        await callback_query.answer()
    else:
        await callback_query.answer()

print("Reached end of user.py", flush=True)