FROM python:3.11

# Обновляем системные пакеты
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Шаг 1: Обновляем базовые утилиты сборщика пакетов
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Шаг 2: Устанавливаем зависимости prophet ЗАРАНЕЕ
RUN pip install --no-cache-dir numpy pandas holidays cmdstanpy

# Шаг 3: Копируем requirements.txt и ставим пакеты с указанием репозитория Т-Банка
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple \
    -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "trade_bot.wsgi"]

