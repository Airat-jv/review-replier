# Используем официальный образ Python
FROM python:3.9

# Установка рабочей директории в контейнере
WORKDIR /app

# Копирование файлов проекта в контейнер
COPY . /app

# Установка зависимостей из файла requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Определение переменных окружения (если необходимо)
ENV TELEGRAM_TOKEN="7417357971:AAH12vfM0llnjH00yJ0S_-RGOAcoGJPhUlc"

# Команда для запуска приложения
CMD ["python", "bot.py"]


