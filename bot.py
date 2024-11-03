import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Получаем токен бота из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить переменную окружения TELEGRAM_TOKEN")

# Инициализируем бота и диспетчер
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Определяем состояния для машины состояний
class Form(StatesGroup):
    choosing_marketplace = State()
    entering_api_key = State()

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Выбрать маркетплейс"]
    keyboard.add(*buttons)
    await message.answer(
        "Здравствуйте! Этот бот поможет вам управлять отзывами на маркетплейсах.",
        reply_markup=keyboard
    )

# Обработчик нажатия кнопки "Выбрать маркетплейс"
@dp.message_handler(lambda message: message.text == "Выбрать маркетплейс")
async def choose_marketplace(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Яндекс.Маркет", "OZON", "Wildberries"]
    keyboard.add(*buttons)
    await Form.choosing_marketplace.set()
    await message.answer("Пожалуйста, выберите маркетплейс:", reply_markup=keyboard)

# Обработчик выбора маркетплейса
@dp.message_handler(state=Form.choosing_marketplace)
async def process_marketplace(message: types.Message, state: FSMContext):
    marketplace = message.text
    if marketplace not in ["Яндекс.Маркет", "OZON", "Wildberries"]:
        await message.answer("Пожалуйста, выберите маркетплейс, используя кнопки ниже.")
        return
    # Сохраняем выбранный маркетплейс в состояние
    await state.update_data(chosen_marketplace=marketplace)
    await message.answer(f"Вы выбрали: {marketplace}")

    if marketplace != "Яндекс.Маркет":
        await message.answer("Извините, этот маркетплейс пока не поддерживается. Пожалуйста, выберите Яндекс.Маркет.")
        return

    # Переходим к вводу API-ключа
    await Form.next()
    await message.answer("Пожалуйста, введите ваш API-ключ для Яндекс.Маркета:")

# Обработчик ввода API-ключа
@dp.message_handler(state=Form.entering_api_key)
async def process_api_key(message: types.Message, state: FSMContext):
    api_key = message.text
    # Здесь можно добавить валидацию API-ключа
    # Сохраняем API-ключ в состоянии или базе данных
    await state.update_data(api_key=api_key)

    # Сохраняем данные (в будущем можно сохранить в базе данных)
    user_data = await state.get_data()
    marketplace = user_data.get('chosen_marketplace')

    await message.answer(f"Ваш API-ключ для {marketplace} сохранен.")
    # Предлагаем получить свежий отзыв
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Получить свежий отзыв"]
    keyboard.add(*buttons)
    await message.answer("Теперь вы можете получить свежий отзыв.", reply_markup=keyboard)

    # Завершаем состояние
    await state.finish()

# Обработчик нажатия кнопки "Получить свежий отзыв"
@dp.message_handler(lambda message: message.text == "Получить свежий отзыв")
async def get_fresh_review(message: types.Message, state: FSMContext):
    # Здесь нужно получить API-ключ из состояния или базы данных
    # Для простоты используем MemoryStorage, в реальном приложении используйте базу данных
    # Получаем данные пользователя
    user_data = await state.get_data()
    api_key = user_data.get('api_key')
    if not api_key:
        await message.answer("Вы еще не ввели API-ключ. Пожалуйста, выберите маркетплейс и введите API-ключ.")
        return

    # Здесь вы можете добавить логику для обращения к API Яндекс.Маркета с использованием api_key
    # Пока что отправим заглушку
    await message.answer("Вот ваш свежий отзыв: ...")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
