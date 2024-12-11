# main.py
import os
import json
import uuid
import requests
import openai
from fastapi import FastAPI, Request, Depends, HTTPException, Body
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

# Убедитесь, что ключ API передан
openai.api_key = os.getenv('OPENAI_API_KEY')

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
    business_id = Column(String)  # Добавили поле для businessId
    business_name = Column(String)  # Добавили поле для businessName
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

# Эндпоинт для первичной авторизации (POST)
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
            if marketplace == 'Яндекс.Маркет':
                # Запрашиваем информацию о бизнесе
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                params = {
                    'page': 1,
                    'pageSize': 1  # Вы можете установить нужный размер страницы
                }
                response = requests.get('https://api.partner.market.yandex.ru/campaigns', headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    campaigns = data.get('campaigns', [])
                    if not campaigns:
                        # Если список кампаний пуст
                        return HTMLResponse(content="<h2>Не найдено ни одной кампании для данного API-ключа.</h2>")
                    else:
                        # Обрабатываем полученные кампании
                        campaign = campaigns[0]
                        business_id = campaign['business']['id']
                        business_name = campaign['business']['name']
                else:
                    return HTMLResponse(content=f"<h2>Ошибка при получении информации о бизнесе: {response.status_code}</h2><pre>{response.text}</pre>")
            else:
                # Для других маркетплейсов
                business_id = None
                business_name = None

            # Сохраняем данные в базе
            new_account = MarketplaceAccount(
                user_id=user.id,
                marketplace=marketplace,
                account_name=business_name or 'Кабинет',
                api_key=api_key,
                business_id=business_id,
                business_name=business_name
            )
            db.add(new_account)

    db.commit()

    # Возвращаем сообщение об успешном сохранении
    bot_username = os.getenv('BOT_USERNAME', 'your_bot_username')
    company_name = company.name if company else "вашей компании"

    return HTMLResponse(content=f"""
    <h2>Здравствуйте, {user.name}!</h2>
    <p>Вы успешно зарегистрировались в системе как сотрудник компании '{company_name}'.</p>
    <p>Вы будете перенаправлены в бот через несколько секунд...</p>
    <script>
        setTimeout(function() {{
            window.location.href = "https://t.me/{bot_username}";
        }}, 3000); // Задержка в 3 секунды
    </script>
    """)
#     <p>Вы можете вернуться в бот, чтобы продолжить работу.</p>
#     <a href="tg://resolve?domain={bot_username}">Перейти в бот</a>

# эндпоинт для добавления кабинетов (GET)
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
                <label for="api_key">API-ключ (OAuth-токен):</label>
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
    api_key = form_data.get('api_key')

    if marketplace == 'Яндекс.Маркет':
        # Запрашиваем информацию о бизнесе
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        params = {
            'page': 1,
            'pageSize': 1  # Вы можете установить нужный размер страницы
        }
        response = requests.get('https://api.partner.market.yandex.ru/campaigns', headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            campaigns = data.get('campaigns', [])
            if not campaigns:
                # Если список кампаний пуст
                return HTMLResponse(content="<h2>Не найдено ни одной кампании для данного API-ключа.</h2>")
            else:
                # Обрабатываем полученные кампании
                campaign = campaigns[0]
                business_id = campaign['business']['id']
                business_name = campaign['business']['name']
        else:
            return HTMLResponse(content=f"<h2>Ошибка при получении информации о бизнесе: {response.status_code}</h2><pre>{response.text}</pre>")
    else:
        # Для других маркетплейсов
        business_id = None
        business_name = None

    # Сохраняем данные в базе
    new_account = MarketplaceAccount(
        user_id=user.id,
        marketplace=marketplace,
        account_name=business_name or 'Кабинет',
        api_key=api_key,
        business_id=business_id,
        business_name=business_name
    )
    db.add(new_account)
    db.commit()

    # Возвращаем сообщение об успешном добавлении
    bot_username = os.getenv('BOT_USERNAME', 'your_bot_username')
    return HTMLResponse(content=f"""
    <h2>Кабинет '{business_name}' успешно добавлен.</h2>
    <p>Маркетплейс: {marketplace}</p>
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
async def get_review(telegram_id: int, account_id: int, page_token: str = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=400, detail='User not authorized')

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == account_id,
        MarketplaceAccount.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail='Marketplace account not found')

    if account.marketplace == 'Яндекс.Маркет':
        review, review_id, next_page_token = get_last_review_yandex(account, page_token)
    else:
        raise HTTPException(status_code=400, detail='Marketplace not supported yet')

    # Генерируем ответ
    if review_id:
        reply = generate_reply_to_review(review)
    else:
        reply = ""

    return {
        'review': review,
        'reply': reply,
        'review_id': review_id,
        'next_page_token': next_page_token
    }


# функция получения отзыва
def get_last_review_yandex(account: MarketplaceAccount, page_token: str = None):
    token = account.api_key

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    business_id = account.business_id
    if not business_id:
        raise HTTPException(status_code=400, detail='Business ID not found for this account')

    url = f'https://api.partner.market.yandex.ru/v2/businesses/{business_id}/goods-feedback'

    # Параметры запроса
    params = {
        'limit': 1
    }
    if page_token:
        params['page_token'] = page_token

    data = {
        'reactionStatus': 'NEED_REACTION',
        'paid': False
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    if response.status_code == 200:
        data = response.json()
        feedbacks = data.get('result', {}).get('feedbacks', [])
        next_page_token = data.get('result', {}).get('paging', {}).get('nextPageToken')
        
        if feedbacks:
            last_feedback = feedbacks[0]
            review_id = last_feedback.get('feedbackId')
            author = last_feedback.get('author', 'Неизвестный автор')
            description = last_feedback.get('description', {})
            advantages = description.get('advantages', '')
            disadvantages = description.get('disadvantages', '')
            comment = description.get('comment', '')
            date = last_feedback.get('createdAt', '')
            rating = last_feedback.get('statistics', {}).get('rating', 'Нет оценки')

            review_text = f"Отзыв от {author} ({date}):\n"
            review_text += f"Оценка: {rating}/5\n\n"
            if advantages:
                review_text += f"Плюсы:\n{advantages}\n\n"
            if disadvantages:
                review_text += f"Минусы:\n{disadvantages}\n\n"
            if comment:
                review_text += f"Комментарий:\n{comment}"

            return review_text, review_id, next_page_token
        else:
            return "Нет доступных отзывов.", None, None
    else:
        return f"Ошибка при получении отзыва: {response.status_code}, {response.text}", None, None
    

# Cинхронная функция для генерации ответа на отзыв
def generate_reply_to_review(review_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Ты профессиональный менеджер по работе с клиентами, который отвечает на отзывы клиентов на маркетплейсе. "
                "Всегда отвечай вежливо и профессионально."
            )
        },
        {
            "role": "user",
            "content": f"Отзыв клиента:\n{review_text}\n\nСгенерируй вежливый и профессиональный ответ на отзыв клиента, не более 200 символов."
        }
    ]

    try:
        # Синхронный вызов API
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        # Используем атрибуты объекта для доступа к данным
        reply = response.choices[0].message.content.strip()
        return reply
    except Exception as e:
        # Логирование ошибки
        print(f"Error in generate_reply_to_review: {e}")
        return "Не удалось сгенерировать ответ на отзыв."
    
# Эндпоинт для 
@app.post('/send_reply')
async def send_reply(data: dict = Body(...), db: Session = Depends(get_db)):
    telegram_id = data.get('telegram_id')
    account_id = data.get('account_id')
    reply_text = data.get('reply')
    review_id = data.get('review_id')  # Получаем review_id из данных

    # Проверяем наличие необходимых данных
    if not all([telegram_id, account_id, reply_text, review_id]):
        raise HTTPException(status_code=400, detail='Missing required data')

    # Остальной код без изменений
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=400, detail='User not authorized')

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == account_id,
        MarketplaceAccount.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail='Marketplace account not found')

    if account.marketplace == 'Яндекс.Маркет':
        success = send_reply_to_yandex_market(account, review_id, reply_text)
        if success:
            return {'status': 'success'}
        else:
            raise HTTPException(status_code=500, detail='Failed to send reply to Yandex Market')
    else:
        raise HTTPException(status_code=400, detail='Marketplace not supported yet')

# Функция отправки ответа
def send_reply_to_yandex_market(account: MarketplaceAccount, review_id: int, reply_text: str) -> bool:
    token = account.api_key
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Используем businessId из аккаунта
    business_id = account.business_id
    if not business_id:
        print("Error: No business_id found for this account")
        return False

    # Новый URL по актуальной документации
    url = f'https://api.partner.market.yandex.ru/businesses/{business_id}/goods-feedback/comments/update'

    data = {
        "feedbackId": review_id,
        "comment": {
            # id не указываем или ставим 0 для создания нового комментария
#             "id": 0,
#             "parentId": 0,
            "text": reply_text
        }
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return True
    else:
        print(f"Error sending reply to Yandex Market: {response.status_code}, {response.text}")
        return False




