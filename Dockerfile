FROM python:3.11-slim

# Установка FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Установка зависимостей Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование скрипта и cookies
COPY bot.py .
COPY cookies.txt .

# Команда для запуска
CMD ["python", "bot.py"]
