import functools

import requests
from celery import shared_task
from django.core.cache import cache


def cache_task_result(timeout=60, key_prefix="celery_cache"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем читаемый ключ: префикс:имя_функции:аргументы
            # Используем str() и убираем лишние пробелы для стабильности
            args_str = ":".join(map(str, args))
            kwargs_str = ":".join(
                f"{k}={v}" for k, v in sorted(kwargs.items())
            )

            cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"

            print(cache_key)

            # Если ключ слишком длинный (Redis не любит ключи > 1кб),
            # можно хешировать аргументы, но тогда ключ станет нечитаемым.
            # Оставим так для удобства отладки.

            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result

        return wrapper

    return decorator


@shared_task
def add_numbers(x, y):
    """Простая задача на сложение"""
    return x + y


@shared_task
@cache_task_result(timeout=60 * 5)
def get_data_moex_index(index: str):
    try:
        url = f"https://iss.moex.com/iss/engines/stock/markets/index/securities/{index}.json"
        params = {
            "iss.meta": "off",
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        securities_data = data.get("marketdata", {})
        columns = securities_data.get("columns", {})
        data = securities_data.get("data", {})[0]
        securities_data = tuple(zip(columns, data))
        if securities_data:
            return {"status": "SUCCESS", "data": securities_data}
        return {"status": "PROGRESS", "data": ""}
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Мосбирже: {e}")
        return {"status": "ERROR", "error": f"{e}"}
    except (KeyError, IndexError, ValueError) as e:
        print(f"Ошибка парсинга данных: {e}")
        return {"status": "ERROR", "error": f"{e}"}
