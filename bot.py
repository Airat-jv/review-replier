# bot.py

import os
import aiohttp
import json
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import BotCommand, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
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

# Создадим класс состояний
class ReviewStates(StatesGroup):
    waiting_for_custom_reply = State()
    confirming_reply = State()

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

    # Получаем информацию о кабинете
    accounts = await get_user_marketplace_accounts(callback_query.from_user.id)
    # Ищем выбранный кабинет по account_id
    account_info = next((acc for acc in accounts if acc['id'] == account_id), None)

    if account_info:
        account_name = account_info.get('account_name')
        marketplace = account_info.get('marketplace')

        # Сохраняем marketplace в данных пользователя
        await storage.update_data(user=callback_query.from_user.id, data={'marketplace': marketplace})

        # Отправляем сообщение с названием кабинета и маркетплейса
        await delete_previous_bot_message(callback_query.from_user.id)
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text=f"Вы выбрали кабинет *{account_name}* на *{marketplace}*.",
            parse_mode=ParseMode.MARKDOWN
        )

        # Отправляем основное меню с кнопкой "Получить свежий отзыв" и иконкой
        await send_main_menu(callback_query.from_user.id, marketplace)
    else:
        await bot.send_message(
            chat_id=callback_query.from_user.id,
            text="Не удалось получить информацию о выбранном кабинете."
        )
    await callback_query.answer()

# Функция для отправки основного меню
async def send_main_menu(user_id: int, marketplace: str):
    # Получаем иконку
    icon = get_marketplace_icon(marketplace)

    # Создаём клавиатуру
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = f"Получить свежий отзыв {icon}"
    keyboard.add(button_text)

    # Отправляем сообщение с клавиатурой
    await bot.send_message(
        chat_id=user_id,
        text="Вы можете выбрать действие:",
        reply_markup=keyboard
    )

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
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    print("Обработчик /start вызван")
    await state.finish()  # Сброс состояния
    is_authorized = await check_authorization(message.from_user.id)
    await delete_previous_bot_message(message.chat.id)  # Удаляем предыдущее сообщение
    if is_authorized:
        # Удаляем клавиатуру
        await message.answer("Пожалуйста, выберите маркетплейс:", reply_markup=types.ReplyKeyboardRemove())

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
        await storage.update_data(user=callback_query.from_user.id, data={'last_bot_message_id': sent_message.message_id})
    else:
        await bot.send_message(callback_query.from_user.id, "У вас нет кабинетов на выбранном маркетплейсе.")
    await callback_query.answer()

# Обработчик кнопки "Получить свежий отзыв"
@dp.message_handler(lambda message: message.text.startswith("Получить свежий отзыв"))
async def get_fresh_review(message: types.Message, state: FSMContext):
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
                reply = data.get('reply')
                review_id = data.get('review_id')  # Получаем review_id из ответа

                # Отправляем отзыв отдельным сообщением
                await message.answer(f"**Свежий отзыв:**\n\n{review}", parse_mode=ParseMode.MARKDOWN)

                # Уведомляем, что сейчас пришлём сгенерированный ответ
#                 await message.answer("Сейчас пришлём вам сгенерированный нейросетью ответ. Если он вас устраивает, можете нажать кнопку 'Отправить предложенный ответ' или можете написать свой.")

                # Отправляем сгенерированный ответ
                await message.answer(f"**Предлагаемый ответ:**\n\n{reply}", parse_mode=ParseMode.MARKDOWN)

                # Сохраняем данные в состоянии, включая review_id
                await state.update_data(
                    review=review,
                    suggested_reply=reply,
                    account_id=account_id,
                    review_id=review_id  # Здесь мы сохраняем review_id
                )

                # Создаём новую клавиатуру с кнопками
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.add("Отправить предложенный ответ", "Написать свой ответ")
                keyboard.add("Отмена")

                await message.answer("Выберите действие:", reply_markup=keyboard)
            else:
                await message.answer("Не удалось получить отзыв. Пожалуйста, попробуйте позже.")

# Обработка нажатий на новые кнопки 
@dp.message_handler(lambda message: message.text in ["Отправить предложенный ответ", "Написать свой ответ"])
async def handle_reply_choice(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if message.text == "Отправить предложенный ответ":
        # Отправляем предложенный ответ
        await send_user_reply(message, state, user_data['suggested_reply'])
    elif message.text == "Написать свой ответ":
        await message.answer("Пожалуйста, напишите ваш ответ на отзыв.")
        await ReviewStates.waiting_for_custom_reply.set()

# Функция для отправки ответа
async def send_user_reply(message: types.Message, state: FSMContext, reply_text: str):
    user_data = await state.get_data()
    # Вызов функции отправки ответа на бэкенд
    success = await send_reply_to_marketplace(
        telegram_id=message.from_user.id,
        account_id=user_data['account_id'],
        review_id=user_data['review_id'],
        reply=reply_text
    )
    if success:
        await message.answer("Ответ успешно отправлен на Яндекс.Маркет.")
    else:
        await message.answer("Не удалось отправить ответ. Пожалуйста, попробуйте позже.")

    # Возвращаем основное меню
    await state.finish()
    await send_main_menu(message, user_data.get('marketplace'))

# Обработка пользовательского ответа
@dp.message_handler(state=ReviewStates.waiting_for_custom_reply)
async def process_custom_reply(message: types.Message, state: FSMContext):
    custom_reply = message.text
    await state.update_data(custom_reply=custom_reply)

    # Подтверждение перед отправкой
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Да, отправить", "Нет, изменить")
    keyboard.add("Отмена")

    await message.answer(f"Вы уверены, что хотите отправить этот ответ?\n\n{custom_reply}", reply_markup=keyboard)
    await ReviewStates.confirming_reply.set()

# Обработка подтверждения
@dp.message_handler(lambda message: message.text in ["Да, отправить", "Нет, изменить"], state=ReviewStates.confirming_reply)
async def process_confirmation(message: types.Message, state: FSMContext):
    if message.text == "Да, отправить":
        user_data = await state.get_data()
        # Отправляем пользовательский ответ
        await send_user_reply(message, state, user_data['custom_reply'])
    elif message.text == "Нет, изменить":
        await message.answer("Пожалуйста, напишите ваш ответ на отзыв.")
        await ReviewStates.waiting_for_custom_reply.set()

# Обработка команды "Отмена"
@dp.message_handler(lambda message: message.text == "Отмена", state='*')
async def cancel_action(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
    # Возвращаем основное меню
    user_data = await storage.get_data(user=message.from_user.id)
    await send_main_menu(message, user_data.get('marketplace'))

###

# Обработчик для callback_query
@dp.callback_query_handler(lambda c: c.data in ['send_suggested_reply', 'write_custom_reply'])
async def process_callback_buttons(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_data = await state.get_data()

    review_id = user_data.get('review_id')  # Получаем review_id из состояния

    if data == 'send_suggested_reply':
        # Отправляем предложенный ответ на Яндекс.Маркет
        await callback_query.message.answer("Отправляем предложенный ответ...")
        # Вызов функции отправки ответа на бэкенд
        success = await send_reply_to_marketplace(
            telegram_id=callback_query.from_user.id,
            account_id=user_data['account_id'],
            review_id=review_id,  # Передаём review_id
            reply=user_data['suggested_reply']
        )
        if success:
            await callback_query.message.answer("Ответ успешно отправлен на Яндекс.Маркет.")
        else:
            await callback_query.message.answer("Не удалось отправить ответ. Пожалуйста, попробуйте позже.")

    elif data == 'write_custom_reply':
        await callback_query.message.answer("Пожалуйста, напишите ваш ответ на отзыв.")
        await ReviewStates.waiting_for_custom_reply.set()

# Обработка пользовательского ответа
@dp.message_handler(state=ReviewStates.waiting_for_custom_reply)
async def process_custom_reply(message: types.Message, state: FSMContext):
    custom_reply = message.text
    await state.update_data(custom_reply=custom_reply)

    # Подтверждение перед отправкой
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Да, отправить", callback_data="confirm_send_reply")
    )
    keyboard.add(
        InlineKeyboardButton("Нет, изменить", callback_data="edit_reply")
    )

    await message.answer(f"Вы уверены, что хотите отправить этот ответ?\n\n{custom_reply}", reply_markup=keyboard)
    await ReviewStates.confirming_reply.set()

# Обработка подтверждения отправки пользовательского ответа
@dp.callback_query_handler(state=ReviewStates.confirming_reply)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_data = await state.get_data()

    if data == 'confirm_send_reply':
        await callback_query.message.answer("Отправляем ваш ответ...")
        # Вызов функции отправки ответа на бэкенд
        success = await send_reply_to_marketplace(
            telegram_id=callback_query.from_user.id,
            account_id=user_data['account_id'],
            review=user_data['review'],
            reply=user_data['custom_reply']
        )
        if success:
            await callback_query.message.answer("Ответ успешно отправлен на Яндекс.Маркет.")
        else:
            await callback_query.message.answer("Не удалось отправить ответ. Пожалуйста, попробуйте позже.")
        await state.finish()

    elif data == 'edit_reply':
        await callback_query.message.answer("Пожалуйста, напишите ваш ответ на отзыв.")
        await ReviewStates.waiting_for_custom_reply.set()

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

