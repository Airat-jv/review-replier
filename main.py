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
    name = Column(String)
    auth_token = Column(String, unique=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'))
    company = relationship("Company", back_populates="users")
    marketplace_accounts = relationship("MarketplaceAccount", back_populates="user")

class MarketplaceAccount(Base):
    __tablename__ = 'marketplace_accounts'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    marketplace = Column(String)
    account_name = Column(String)
    api_key = Column(String)
    user = relationship("User", back_populates="marketplace_accounts")

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
        company = user.company

    # Обработка маркетплейсов и API-ключей
    supported_marketplaces = ["Яндекс.Маркет", "OZON", "Wildberries"]
    for marketplace in supported_marketplaces:
        api_key = form_data.get(f"{marketplace}_api_key")
        if api_key:
            account_name = form_data.get(f"{marketplace}_account_name", f"Кабинет {marketplace}")
            new_account = MarketplaceAccount(
                user_id=user.id,
                marketplace=marketplace,
                account_name=account_name,
                api_key=api_key
            )
            db.add(new_account)

    db.commit()

    # Возвращаем сообщение об успешном сохранении
    bot_username = os.getenv('BOT_USERNAME', 'your_bot_username')
    company_name = company.name if company else "вашей компании"

    return HTMLResponse(content=f"""
    <h2>Данные успешно сохранены.</h2>
    <p>Вы можете вернуться в бот, чтобы продолжить работу.</p>
    <a href="tg://resolve?domain={bot_username}">Перейти в бот</a>
    """)

# эндпоинт для добавления кабинетов
@app.get('/add_marketplace', response_class=HTMLResponse)
async def add_marketplace_form(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.auth_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail='Invalid token')

    supported_marketplaces = ["Яндекс.Маркет", "OZON", "Wildberries"]

    marketplaces_options = ''.join([f'<option value="{mp}">{mp}</option>' for mp in supported_marketplaces])

    html_content = f"""
    <html>
        <head>
            <title>Добавить кабинет маркетплейса</title>
        </head>
        <body>
            <h1>Добавьте новый кабинет маркетплейса</h1>
            <form action="/add_marketplace" method="post">
                <input type="hidden" name="token" value="{token}">
                <label for="marketplace">Маркетплейс:</label>
                <select id="marketplace" name="marketplace">
                    {marketplaces_options}
                </select><br><br>
                <label for="account_name">Название кабинета:</label>
                <input type="text" id="account_name" name="account_name" required><br><br>
                <label for="api_key">API-ключ:</label>
                <input type="text" id="api_key" name="api_key" required><br><br>
                <button type="submit">Сохранить</button>
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Обработчик формы (POST)
@app.post('/add_marketplace', response_class=HTMLResponse)
async def add_marketplace_submit(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    token = form_data.get('token')
    user = db.query(User).filter(User.auth_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail='Invalid token')

    marketplace = form_data.get('marketplace')
    account_name = form_data.get('account_name')
    if not account_name:
        return HTMLResponse(content="<h2>Название кабинета обязательно для заполнения.</h2>")
    api_key = form_data.get('api_key')

    new_account = MarketplaceAccount(
        user_id=user.id,
        marketplace=marketplace,
        account_name=account_name,
        api_key=api_key
    )
    db.add(new_account)
    db.commit()

    # Возвращаем сообщение об успешном сохранении
    bot_username = os.getenv('BOT_USERNAME', 'your_bot_username')

    return HTMLResponse(content=f"""
    <h2>Кабинет успешно добавлен.</h2>
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
    if user:
        # Проверяем, что у пользователя есть имя и компания
        if not user.name or not user.company_id:
            return {'authorized': False}
        # Проверяем, есть ли у пользователя хотя бы один кабинет маркетплейса
        accounts = db.query(MarketplaceAccount).filter(MarketplaceAccount.user_id == user.id).all()
        if accounts:
            return {'authorized': True}
        else:
            # Если нет кабинетов, но есть имя и компания, считаем пользователя авторизованным
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

# # Эндпоинт для получения списка маркетплейсов пользователя
# Эндпоинт для получения кабинетов пользователя
@app.get('/get_user_marketplace_accounts')
async def get_user_marketplace_accounts(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        accounts = db.query(MarketplaceAccount).filter(MarketplaceAccount.user_id == user.id).all()
        return {'accounts': [
            {
                'id': account.id,
                'marketplace': account.marketplace,
                'account_name': account.account_name
            } for account in accounts
        ]}
    else:
        return {'accounts': []}

# Эндпоинт для получения свежего отзыва
@app.get('/get_review')
async def get_review(telegram_id: int, account_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=400, detail='User not authorized')

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == account_id,
        MarketplaceAccount.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail='Marketplace account not found')

    # Здесь реализуйте логику получения отзыва, используя account.api_key
    review = f"Пример отзыва с {account.marketplace} - {account.account_name}"

    return {'review': review}
