# ReviewReplier
# main.py
import os
import json
import uuid
import requests
import openai
import datetime
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

class Campaign(Base):
    __tablename__ = 'campaigns'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с MarketplaceAccount (который хранит api_key, business_id и т.д.)
    marketplace_account_id = Column(Integer, ForeignKey('marketplace_accounts.id'))

    # Собственно ID кампании на Я.Маркете
    campaign_id = Column(Integer, index=True)  
    domain = Column(String)
    name = Column(String)           # Например, "BlackSwan"
    placement_type = Column(String) # "FBY", "FBS" и т. п.

    # Допустим, если нужно хранить ещё какие-то поля из campaigns.

    # Связь обратно, если нужно
    account = relationship("MarketplaceAccount", back_populates="campaigns")

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

    campaigns = relationship("Campaign", back_populates="account")

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
                # запрос /campaigns
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                params = {
                    'page': 1,
                    'pageSize': 50  # Получим побольше кампаний
                }
                response = requests.get('https://api.partner.market.yandex.ru/campaigns', headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    campaigns = data.get('campaigns', [])
                    if not campaigns:
                        return HTMLResponse(content="<h2>Не найдено ни одной кампании для данного API-ключа.</h2>")
                    else:
                        # Берём business_id и business_name из первой кампании
                        camp0 = campaigns[0]
                        business_id = camp0['business']['id']
                        business_name = camp0['business']['name']
                else:
                    return HTMLResponse(content=f"<h2>Ошибка: {response.status_code}</h2><pre>{response.text}</pre>")

            # Создаём MarketplaceAccount
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
            db.refresh(new_account)  # чтобы получить new_account.id

            # Теперь сохраняем все кампании
            if marketplace == 'Яндекс.Маркет':
                for camp in campaigns:
                    new_camp = Campaign(
                        marketplace_account_id=new_account.id,
                        campaign_id=camp['id'],
                        domain=camp.get('domain'),
                        name=camp.get('name'),
                        placement_type=camp.get('placementType')
                    )
                    db.add(new_camp)

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
        review, review_id, next_page_token, short_data = get_last_review_yandex(account, page_token, db)
    else:
        raise HTTPException(status_code=400, detail='Marketplace not supported yet')

    # Генерируем ответ
    review, review_id, next_page_token, short_data = get_last_review_yandex(account, page_token, db)
    if review_id:
        # Вызываем новую версию generate_reply_to_review, 
        # куда передадим short_data
        reply = generate_reply_to_review(short_data)
    else:
        reply = ""

    # Извлекаем photos из short_data
    photos = short_data.get("photos", [])

    # Лог перед тем, как вернуть данные
    response_data = {
        'review': review,
        'reply': reply,
        'review_id': review_id,
        'next_page_token': next_page_token,
        'photos': photos
    }

    return response_data

# Функция для форматирования даты
def format_yandex_date(date_str: str) -> str:
    """
    Принимает дату в формате "2025-01-27T11:35:23.1+03:00"
    и возвращает "27.01.2025 11:35 Мск"
    """
    
    try:
        # Попробуем встроенный fromisoformat (Python 3.7+)
        parsed = datetime.datetime.fromisoformat(date_str)
    except ValueError:
        # Если не получилось, используем dateutil, который более гибкий
        from dateutil import parser
        parsed = parser.isoparse(date_str)
    
    return parsed.strftime("%d.%m.%Y %H:%M") + " Мск"

# функция получения отзыва
def get_last_review_yandex(account: MarketplaceAccount, page_token: str, db: Session):
    """
    Получает последний отзыв с Яндекс.Маркета (goods-feedback) для данного account.
    Если находим orderId в отзыве, пытаемся определить SKU и название товара,
    пройдя по всем кампаниям данного аккаунта.
    """

    token = account.api_key
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    business_id = account.business_id
    if not business_id:
        return ("Ошибка: business_id не найден", None, None)

    # URL для получения отзывов
    url = f'https://api.partner.market.yandex.ru/v2/businesses/{business_id}/goods-feedback'
    
    # Параметры запроса
    params = {
        'limit': 1  # берем 1 отзыв
    }
    if page_token:
        params['page_token'] = page_token
    
    data = {
        'reactionStatus': 'NEED_REACTION',
        'paid': False
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    if response.status_code != 200:
        return (f"Ошибка при получении отзыва: {response.status_code}, {response.text}", None, None)

    data = response.json()
    feedbacks = data.get('result', {}).get('feedbacks', [])
    next_page_token = data.get('result', {}).get('paging', {}).get('nextPageToken')

    if not feedbacks:
        return ("Нет доступных отзывов.", None, None)

    # Берём первый (последний) отзыв
    last_feedback = feedbacks[0]
    review_id = last_feedback.get('feedbackId')
    author = last_feedback.get('author', 'Неизвестный автор')
    description = last_feedback.get('description', {})
    advantages = description.get('advantages', '')
    disadvantages = description.get('disadvantages', '')
    comment = description.get('comment', '')
    raw_date = last_feedback.get('createdAt', '')
    formatted_date = format_yandex_date(raw_date)
    rating = last_feedback.get('statistics', {}).get('rating', 'Нет оценки')
    media = last_feedback.get('media', {})
    photos = media.get('photos', [])

    # Базовый текст отзыва
    review_text = f"Отзыв от {author} ({formatted_date}):\n"
    review_text += f"Оценка: {rating}/5\n\n"
    if advantages:
        review_text += f"Плюсы:\n{advantages}\n\n"
    if disadvantages:
        review_text += f"Минусы:\n{disadvantages}\n\n"
    if comment:
        review_text += f"Комментарий:\n{comment}"

    # Новая логика: ищем SKU и название товара
    order_id = last_feedback.get('identifiers', {}).get('orderId')
    if order_id:
        # Достаём все кампании данного аккаунта
        campaigns = db.query(Campaign).filter(Campaign.marketplace_account_id == account.id).all()

        offer_id = None
        offer_name = None
        placement_type = None

        for camp in campaigns:
            # пытаемся найти заказ в данной кампании
            oi, oname = get_item_info_yandex(account.api_key, camp.campaign_id, order_id)
            if oi and oname:
                offer_id = oi
                offer_name = oname
                placement_type = camp.placement_type  # "FBY", "FBS" и т.д.
                break

        if offer_id and offer_name:
            review_text += f"\n\nТовар: {offer_name} (SKU: {offer_id})"
            # Добавим id заказа
            review_text += f"\nЗаказ №{order_id}"
            if placement_type:
                review_text += f"\nМодель работы: {placement_type}"

    short_data = {
        "author": author,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "comment": comment,
        "product_name": offer_name,
        "photos": photos,
        "seller_name": account.account_name
        }

    return (review_text, review_id, next_page_token, short_data)


def get_item_info_yandex(api_key: str, campaign_id: int, order_id: int):
    """
    Пытается сделать GET /campaigns/{campaignId}/orders/{orderId}
    Если удаётся найти items, возвращаем (offerId, offerName) (первый item, для примера).
    Если не найден, возвращаем (None, None).
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    url = f"https://api.partner.market.yandex.ru/campaigns/{campaign_id}/orders/{order_id}"

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get('order', {}).get('items', [])
        if items:
            item = items[0]
            offer_id = item.get('offerId')
            offer_name = item.get('offerName')
            return (offer_id, offer_name)
        else:
            return (None, None)
    else:
        # заказ не найден в этой кампании (или нет доступа)
        return (None, None)
    

# Cинхронная функция для генерации ответа на отзыв
def generate_reply_to_review(short_data: dict) -> str:
    author = short_data.get('author') or "Неизвестно"
    pluses = short_data.get('advantages') or ""
    minuses = short_data.get('disadvantages') or ""
    comment = short_data.get('comment') or ""
    product_name = short_data.get('product_name') or "неизвестный товар"
    seller_name = short_data.get('seller_name') or "неизвестном продавце"

    # Сформируем короткий текст отзыва
    user_prompt = f"Отзыв от {author} о товаре '{product_name}' у продавца '{seller_name}':\n"
    if pluses:
        user_prompt += f"Плюсы: {pluses}\n"
    if minuses:
        user_prompt += f"Минусы: {minuses}\n"
    if comment:
        user_prompt += f"Комментарий: {comment}\n"

    messages = [
        {
            "role": "system",
            "content": (
                "Ты эксперт по управлению репутацией брендов. Ты пишешь ответы на отзывы клиентов продавца на маркетплейсах. "
                "Ответы должны акцентировать внимание на положительных качествах товара, развивая их и минимизируя негатив, "
                "предлагая альтернативы. Все для укрепления доверия потенциальных покупателей."
            )
        },
        {
            "role": "user",
            "content": (
                f"{user_prompt}\n"
                "Сгенерируй вежливый и профессиональный ответ на отзыв клиента, не более 280 символов."
            )
        }
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=280,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        return reply
    except Exception as e:
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




