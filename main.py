# main.py

import os
import json
import uuid
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

# Настройка CORS (если необходимо)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка базы данных
DB_USER = os.getenv('DB_USER', 'your_db_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'your_db_password')
DB_NAME = os.getenv('DB_NAME', 'your_db_name')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = os.getenv('DB_PORT', '5432')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели
class Company(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    users = relationship("User", back_populates="company")

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    name = Column(String)  # Добавили поле для имени сотрудника
    auth_token = Column(String, unique=True, index=True)
    api_keys = Column(String)
    marketplaces = Column(String)
    company_id = Column(Integer, ForeignKey('companies.id'))
    company = relationship("Company", back_populates="users")

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Dependency для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Эндпоинт для авторизации (GET)
@app.get('/auth', response_class=HTMLResponse)
async def auth_form(token: str, action: str = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.auth_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail='Invalid token')

    # Определяем, первая это авторизация или добавление маркетплейсов
    is_first_authorization = action != 'add_marketplace'

    supported_marketplaces = ["Яндекс.Маркет", "OZON", "Wildberries"]

    fields_html = ""
    for marketplace in supported_marketplaces:
        disabled = ""
        if marketplace not in ["Яндекс.Маркет"]:
            disabled = "disabled"
        fields_html += f"""
        <h3>{marketplace}</h3>
        <label for="{marketplace}_api_key">API-ключ:</label>
        <input type="text" id="{marketplace}_api_key" name="{marketplace}_api_key" {disabled}><br><br>
        """

    # Формируем форму в зависимости от действия
    if is_first_authorization:
        form_fields = f"""
            <label for="name">Ваше имя:</label>
            <input type="text" id="name" name="name" required><br><br>
            <label for="company_code">Код компании:</label>
            <input type="text" id="company_code" name="company_code" required><br><br>
            {fields_html}
        """
    else:
        form_fields = fields_html

    html_content = f"""
    <html>
        <head>
            <title>Авторизация</title>
        </head>
        <body>
            <h1>Введите ваши данные</h1>
            <form action="/auth" method="post">
                <input type="hidden" name="token" value="{token}">
                <input type="hidden" name="action" value="{action}">
                {form_fields}
                <button type="submit">Сохранить</button>
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Эндпоинт для авторизации (POST)
@app.post('/auth', response_class=HTMLResponse)
async def auth_submit(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    token = form_data.get('token')
    action = form_data.get('action')
    user = db.query(User).filter(User.auth_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail='Invalid token')

    is_first_authorization = action != 'add_marketplace'

    if is_first_authorization:
        name = form_data.get('name')
        if name:
            user.name = name
        else:
            return HTMLResponse(content="<h2>Имя обязательно для заполнения.</h2>")

        company_code = form_data.get('company_code')
        if company_code:
            company = db.query(Company).filter(Company.code == company_code).first()
            if not company:
                return HTMLResponse(content="<h2>Неверный код компании. Пожалуйста, попробуйте снова.</h2>")
            user.company_id = company.id
        else:
            return HTMLResponse(content="<h2>Код компании обязателен для заполнения.</h2>")
    else:
        # При добавлении маркетплейсов используем существующую информацию
        company = user.company

    # Обработка маркетплейсов и API-ключей
    api_keys = json.loads(user.api_keys) if user.api_keys else {}
    marketplaces = json.loads(user.marketplaces) if user.marketplaces else []

    supported_marketplaces = ["Яндекс.Маркет", "OZON", "Wildberries"]
    for marketplace in supported_marketplaces:
        api_key = form_data.get(f"{marketplace}_api_key")
        if api_key:
            api_keys[marketplace] = api_key
            if marketplace not in marketplaces:
                marketplaces.append(marketplace)

    user.api_keys = json.dumps(api_keys)
    user.marketplaces = json.dumps(marketplaces)

    db.commit()

    # Возвращаем сообщение об успешном сохранении
    bot_username = os.getenv('BOT_USERNAME', 'your_bot_username')
    company_name = company.name if company else "вашей компании"

    return HTMLResponse(content=f"""
    <h2>Данные успешно сохранены.</h2>
    <p>Вы можете вернуться в бот, чтобы продолжить работу.</p>
    <a href="tg://resolve?domain={bot_username}">Перейти в бот</a>
    """)

# Эндпоинт для генерации токена и сохранения пользователя
from pydantic import BaseModel

class TokenRequest(BaseModel):
    telegram_id: int

@app.post('/generate_token')
async def generate_token(request: TokenRequest, db: Session = Depends(get_db)):
    telegram_id = request.telegram_id
    token = str(uuid.uuid4())
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.auth_token = token
    else:
        user = User(telegram_id=telegram_id, auth_token=token)
        db.add(user)
    db.commit()
    return {'token': token}

# Эндпоинт для проверки авторизации пользователя
@app.get('/is_authorized')
async def is_authorized(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user and user.api_keys:
        api_keys = json.loads(user.api_keys)
        if api_keys:
            return {'authorized': True}
    return {'authorized': False}

# Эндпоинт для получения информации о пользователе
@app.get('/user_info')
async def user_info(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        return {
            'name': user.name,
            'auth_token': user.auth_token
        }
    else:
        raise HTTPException(status_code=404, detail='User not found')

# Эндпоинт для получения списка маркетплейсов пользователя
@app.get('/get_user_marketplaces')
async def get_user_marketplaces(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user and user.marketplaces:
        marketplaces = json.loads(user.marketplaces)
        return {'marketplaces': marketplaces}
    else:
        return {'marketplaces': []}

# Эндпоинт для получения свежего отзыва
@app.get('/get_review')
async def get_review(telegram_id: int, marketplace: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.api_keys:
        raise HTTPException(status_code=400, detail='User not authorized or no API keys found')

    api_keys = json.loads(user.api_keys)
    api_key = api_keys.get(marketplace)
    if not api_key:
        raise HTTPException(status_code=400, detail='No API key for the selected marketplace')

    # Здесь реализуйте логику получения отзыва с выбранного маркетплейса, используя соответствующий API-ключ
    review = f"Пример отзыва с {marketplace}"

    return {'review': review}
