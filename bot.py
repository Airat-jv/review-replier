# ReviewReplier
# bot.py

import os
import aiohttp
import json
import re
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import BotCommand, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, InputMediaPhoto, MediaGroup
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

def escape_markdown_v2(text: str) -> str:
    """
    Экранирует спецсимволы Telegram Markdown V2.
    """
    pattern = r'([*_`$begin:math:display$$end:math:display$()~>#+\-=|{}.!])'
    return re.sub(pattern, r'\\\1', text)

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
            callback_data = f"select_account:{accs[0]['id']}"
            button = InlineKeyboardButton(text=f"{mp} - {accs[0]['account_name']}", callback_data=callback_data)
            keyboard.add(button)
        else:
            callback_data = f"choose_account:{mp}"
            button = InlineKeyboardButton(text=f"{mp}", callback_data=callback_data)
            keyboard.add(button)

    # Передаем chat_id и user_id одинаково
    await delete_previous_bot_message(chat_id, chat_id)
    sent_message = await bot.send_message(chat_id, "Пожалуйста, выберите маркетплейс или кабинет:", reply_markup=keyboard)
    await storage.update_data(chat=chat_id, user=chat_id, data={'last_bot_message_id': sent_message.message_id})


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
    
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    await storage.update_data(chat=chat_id, user=user_id, data={'last_bot_message_id': sent_message.message_id})

    await callback_query.answer()

# Функция для Обработать выбор кабинет
@dp.callback_query_handler(lambda c: c.data.startswith('select_account:'))
async def process_select_account(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    account_id = int(callback_query.data.split(':')[1])

    # Сначала получаем account_info
    accounts = await get_user_marketplace_accounts(user_id)
    account_info = next((acc for acc in accounts if acc['id'] == account_id), None)

    if account_info is None:
        await bot.send_message(chat_id, "Не удалось получить информацию о выбранном кабинете.")
        return

    # Теперь, когда мы знаем account_info, мы можем использовать его
    marketplace = account_info.get('marketplace')
    user_data['selected_account_id'] = account_id
    user_data['marketplace'] = marketplace
    user_data['next_page_token'] = None
    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

    account_name = account_info.get('account_name')

    await delete_previous_bot_message(chat_id, user_id)
    await bot.send_message(
        chat_id=chat_id,
        text=f"Вы выбрали кабинет *{account_name}* на *{marketplace}*.",
        parse_mode=ParseMode.MARKDOWN
    )

    await send_main_menu(user_id, marketplace)
    await callback_query.answer()

# Функция для отправки основного меню
async def send_main_menu(user_id: int, marketplace: str):

    # Создаём клавиатуру
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = "Получить отзыв"
    keyboard.add(button_text)

    # Отправляем сообщение с клавиатурой
    await bot.send_message(
        chat_id=user_id,
        text="Вы можете выбрать действие:",
        reply_markup=keyboard
    )

# Функция для удаления предыдущего сообщения бота
async def delete_previous_bot_message(chat_id, user_id):
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    last_message_id = user_data.get('last_bot_message_id')
    if last_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        except:
            pass  # Если сообщение уже удалено или недоступно

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # Если нужно очистить данные, делаем это через user_data
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    user_data.clear()
    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

    # Далее логика старта без state.finish()
    is_authorized = await check_authorization(message.from_user.id)
    await delete_previous_bot_message(chat_id, user_id)  # Удаляем предыдущее сообщение
    if is_authorized:
        # Удаляем клавиатуру
        await message.answer("Пожалуйста, выберите маркетплейс:", reply_markup=types.ReplyKeyboardRemove())

        user_info = await get_user_info(message.from_user.id)
        name = user_info.get('name', '')
        auth_token = user_info.get('auth_token', '')
        if not auth_token:
            auth_token = await generate_token(message.from_user.id)
        safe_name = escape_markdown_v2(name)
        greeting = f"Здравствуйте, {safe_name}! Добро пожаловать в *ReviewReplierBot*!\n\n"
        welcome_text = (
            f"{greeting}"
            "Этот бот поможет вам управлять отзывами на маркетплейсах. Вы можете получать свежие отзывы и быстро отвечать на них с помощью интеграции с ChatGPT.\n\n"
            "Выберите нужное действие ниже:"
        )
        # Отправляем инлайн-кнопки для выбора маркетплейса
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
        await storage.update_data(chat=chat_id, user=message.from_user.id, data={'last_bot_message_id': sent_message.message_id})
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
        await storage.update_data(chat=chat_id, user=message.from_user.id, data={'last_bot_message_id': sent_message.message_id})

# Обработчик команды /help
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)
    await delete_previous_bot_message(chat_id, user_id)  # В delete_previous_bot_message тоже нужно изменить сигнатуру
    
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
    user_data['last_bot_message_id'] = sent_message.message_id
    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

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
    await storage.update_data(chat=chat_id, user=callback_query.from_user.id, data={'selected_marketplace': marketplace})
    # Создаём обычную клавиатуру с кнопкой "Получить свежий отзыв"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = f"Получить отзыв {get_marketplace_icon(marketplace)}"
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
    await storage.update_data(chat=chat_id, user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})

# Обработчик для выбора маркетплейса, который затем предлагает выбрать кабинет
@dp.callback_query_handler(lambda c: c.data.startswith('choose_marketplace:'))
async def process_choose_marketplace(callback_query: types.CallbackQuery):
    marketplace = callback_query.data.split(':')[1]
    accounts = await get_user_marketplace_accounts(callback_query.from_user.id)
    accounts = [acc for acc in accounts if acc['marketplace'] == marketplace]

    if accounts:
        keyboard = InlineKeyboardMarkup(row_width=1)
        for acc in accounts:
            callback_data = f"select_account:{acc['id']}"
            button = InlineKeyboardButton(text=acc['account_name'], callback_data=callback_data)
            keyboard.add(button)
        await delete_previous_bot_message(callback_query.from_user.id)
        sent_message = await bot.send_message(callback_query.from_user.id, "Выберите кабинет:", reply_markup=keyboard)
        await storage.update_data(chat=chat_id, user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})
    else:
        await bot.send_message(callback_query.from_user.id, "У вас нет кабинетов на выбранном маркетплейсе.")
    await callback_query.answer()

# Обработчик кнопки "Получить отзыв" и еще "Перейти к следующему"
@dp.message_handler(lambda message: message.text in ["Получить отзыв", "Перейти к следующему"])
async def handle_review_actions(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    # Отправляем промежуточное сообщение
    loading_message = await message.answer("🤖Получаем данные… \n✨Генерируем ответ… ")

    user_data = await storage.get_data(chat=chat_id, user=user_id)
    account_id = user_data.get('selected_account_id')
    if not account_id:
        # Перед тем как ответить пользователю, удаляем промежуточное сообщение
        await bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        await message.answer("Сначала выберите кабинет. Нажмите /start для выбора.")
        return

    # Определяем, нужно ли использовать next_page_token
    page_token = None
    if "Перейти к следующему" in message.text:
        page_token = user_data.get('next_page_token')

    # Делаем запрос к бэкенду
    params = {
        'telegram_id': user_id,
        'account_id': account_id
    }
    if page_token:
        params['page_token'] = page_token

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/get_review", params=params) as resp:

            # Удаляем промежуточное сообщение перед тем как отправить итоговый ответ
            await bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)

            if resp.status == 200:
                data = await resp.json()
                review = data.get('review')
                reply = data.get('reply')
                review_id = data.get('review_id')
                new_next_page_token = data.get('next_page_token')
                photos = data.get('photos', [])

                if review_id:
                    # Сохраняем данные
                    user_data['review'] = review
                    user_data['suggested_reply'] = reply
                    user_data['review_id'] = review_id
                    user_data['next_page_token'] = new_next_page_token
                    user_data['current_mode'] = None
                    await storage.update_data(chat=chat_id, user=user_id, data=user_data)

                    # Отправляем основной текст
                    safe_review = escape_markdown_v2(review)
                    await message.answer(f"**Отзыв:**\n\n{safe_review}", parse_mode=ParseMode.MARKDOWN_V2)

                    # Отправляем фото (если есть)
                    if photos:
                        if len(photos) == 1:
                            await message.answer_photo(photo=photos[0])
                        else:
                            media_group = MediaGroup()
                            for p_url in photos:
                                media_group.attach_photo(InputMediaPhoto(p_url))
                            await message.answer_media_group(media_group)
                    
                    # Отправляем предложенный ответ
                    safe_reply = escape_markdown_v2(reply)
                    await message.answer(f"**Предлагаемый ответ:**\n\n{safe_reply}", parse_mode=ParseMode.MARKDOWN_V2)

                    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
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

# Обработка нажатий на новые кнопки 
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

# Функция отправки ответа на Яндекс.Маркет
async def send_user_reply(message: types.Message, custom_reply: str) -> bool:
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    account_id = user_data.get('selected_account_id')
    review_id = user_data.get('review_id')

    if not account_id or not review_id:
        # Если не хватает данных, возвращаем False
        return False

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/send_reply", json={
            'telegram_id': user_id,
            'account_id': account_id,
            'review_id': review_id,
            'reply': custom_reply
        }) as resp:
            return resp.status == 200

# Обработка подтверждения отправки пользовательского ответа (когда мы уже на этапе подтверждения)
@dp.message_handler(lambda message: message.text in ["Да, отправить", "Нет, изменить"])
async def process_confirmation(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    if user_data.get('current_mode') == 'confirming_reply':
        if message.text == "Да, отправить":
            await message.answer("Отправляем ваш ответ...")
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

# Обработка пользовательского ответа
@dp.message_handler(lambda message: True)  # был catch-all
async def process_custom_reply(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_data = await storage.get_data(chat=chat_id, user=user_id)

    # Проверяем, действительно ли мы ожидали пользовательского ответа
    # Например, если current_mode = 'waiting_for_custom_reply'
    if user_data.get('current_mode') == 'waiting_for_custom_reply':
        custom_reply = message.text
        user_data['custom_reply'] = custom_reply
        # Переходим в режим подтверждения
        user_data['current_mode'] = 'confirming_reply'
        await storage.update_data(chat=chat_id, user=user_id, data=user_data)

        # Показываем кнопки подтверждения
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("Да, отправить", "Нет, изменить")

        await message.answer(f"Вы уверены, что хотите отправить этот ответ?\n\n{custom_reply}", reply_markup=keyboard)
    else:
        # Если мы не в режиме ожидания ответа, можно игнорировать или сообщить пользователю
        # Например:
        await message.answer("Сейчас не ожидается пользовательский ответ.")

# Функция для отправки ответа на Яндекс.Маркет
async def send_reply_to_marketplace(telegram_id: int, account_id: int, review_id: int, reply: str) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/send_reply", json={
            'telegram_id': telegram_id,
            'account_id': account_id,
            'review_id': review_id,  # Передаём review_id
            'reply': reply
        }) as resp:
            if resp.status == 200:
                return True
            else:
                return False

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

