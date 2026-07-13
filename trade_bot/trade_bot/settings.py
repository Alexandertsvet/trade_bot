import datetime
import os
from dotenv import load_dotenv

load_dotenv()

import logging
from pathlib import Path
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX
from data.clickhouse_module import ClickHouseProcessor

logger = logging.getLogger(__name__)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} [{asctime}] {module}  {name}.{funcName}:{lineno} [PID:{process:d} {thread:d} ] -> {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file_info": {
            "level": "INFO",
            # Используем наш кастомный класс (указываем его как объект или строку, если он импортирован)
            "()": "trade_bot.logging_handlers.CustomTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "info.log"),
            "when": "MIDNIGHT",
            "atTime": datetime.time(0, 0, 0),  # Время ротации ровно в 00:00:00
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "file_django": {
            "level": "WARNING",
            "()": "trade_bot.logging_handlers.CustomTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django.log"),
            "when": "MIDNIGHT",
            "atTime": datetime.time(0, 0, 0),  # Время ротации ровно в 00:00:00
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "file_errors": {
            "level": "ERROR",
            "()": "trade_bot.logging_handlers.CustomTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "error.log"),
            "when": "MIDNIGHT",
            "atTime": datetime.time(0, 0, 0),  # Время ротации ровно в 00:00:00
            "backupCount": 60,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file_info", "file_django", "file_errors"],
            "level": "INFO",
        },
        "django": {
            "handlers": ["console", "file_info", "file_django"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!

SECRET_KEY = os.getenv("SECRET_KEY")
SALT_KEY = os.getenv("SALT_KEY")
ALGOPACK_KEY = os.getenv("ALGOPACK_KEY")
pg_db_name = os.getenv("pg_db_name")
pg_user = os.getenv("pg_user")
pg_password = os.getenv("pg_password")
pg_host = os.getenv("pg_host")
pg_port = os.getenv("pg_port")
TINKOFF_TOKEN_SANDBOX = os.getenv("TINKOFF_TOKEN_SANDBOX")


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

if DEBUG:
    TARGET_TRADE = INVEST_GRPC_API_SANDBOX
else:
    TARGET_TRADE = INVEST_GRPC_API

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "user.apps.UserConfig",
    "t_invest.apps.TInvestConfig",
    "homepage.apps.HomepageConfig",
    "data.apps.DataConfig",
    "bot.apps.BotConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trade_bot.urls"
TEMPLATES_DIR = BASE_DIR / "templates"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "data.context_processors.current_time.current_time",
            ],
            "string_if_invalid": "ДАННЫЕ ОТСУТСВУЮТ",
        },
    },
]

WSGI_APPLICATION = "trade_bot.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases


"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': pg_db_name,
        'USER': pg_user,
        'PASSWORD': pg_password,
        'HOST': pg_host,
        'PORT': pg_port,
        'OPTIONS': {
            'options': '-c search_path=public'
        },
    }
}
"""

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("pg_db_name", "trade_bor"),
        "USER": os.environ.get("pg_user", "trade_bor_user"),
        "PASSWORD": os.environ.get("pg_password", "Tsvetkov_19"),
        "HOST": os.environ.get("pg_host", "postgres"),
        "PORT": os.environ.get("pg_port", "5432"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


IS_DOCKER = os.getenv("DOCKER_ENV", "False").lower() in ("true", "1", "t")
print(f"Запущено в Docker: {IS_DOCKER}")

if IS_DOCKER:
    # В Docker контейнере
    CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379")
else:
    # Локальная разработка без Docker
    CELERY_BROKER_URL = "redis://localhost:6379"
    CELERY_RESULT_BACKEND = "redis://localhost:6379"

# Переопределяем параметры базы данных, если мы НЕ в Docker
if not IS_DOCKER:
    DATABASES["default"]["HOST"] = "localhost"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Moscow"

###
AUTH_USER_MODEL = "user.User"

DATE_INPUT_FORMATS = "%d.%m.%Y"

LOGIN_REDIRECT_URL = "homepage:home"
LOGOUT_REDIRECT_URL = "user:login"
LOGIN_URL = "user:login"

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / "email"
DEFAULT_FROM_EMAIL = "tb@mail.ru"

# Инициализируем ClickHouse (убедитесь, что внутри класса используется os.getenv('CLICKHOUSE_HOST'))
client_clickhouse = ClickHouseProcessor()

print(client_clickhouse)
print(client_clickhouse.execute("SELECT version();"))
