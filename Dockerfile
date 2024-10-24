# Базовый образ, используем официальный образ Python
FROM python:3.9

# Установка рабочей директории в контейнере
WORKDIR /app

# Копирование файлов проекта в контейнер
COPY . /app

# Установка зависимостей из файла requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Определение переменных окружения (если необходимо)
ENV API_KEY="Your_API_Key"

# Команда для запуска приложения
CMD ["python", "main.py"]
