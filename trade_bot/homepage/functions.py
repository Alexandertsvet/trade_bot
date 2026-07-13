import requests
from django.core.cache import cache


def get_moex_index_value_direct(index: str):
    """
    Получает значение индекса IMOEX прямым запросом к API Мосбиржи.

    Ваше название поля	Название в API ISS (JSON)	Описание
    SECID	SECID	Идентификатор инструмента (тикер)
    BOARDID	BOARDID	Идентификатор режима торгов (например, TQBR)
    LASTVALUE	LAST	Цена последней сделки
    OPENVALUE	OPEN	Цена открытия
    CURRENTVALUE	CURRENTVALUE	Текущая цена (аналог последней)
    LASTCHANGE	CHANGE	Абсолютное изменение цены
    LASTCHANGETOOPENPRC	CHANGETOOPENPRC	Изменение к открытию, в процентах
    UPDATETIME	UPDATETIME	Время последнего обновления
    LASTCHANGEPRC	LASTCHANGEPRC	Изменение цены последней сделки, в процентах
    VALTODAY	VALTODAY	Оборот в рублях
    MONTHCHANGEPRC	MONTHCHANGEPRC	Изменение с начала месяца, %
    YEARCHANGEPRC	YEARCHANGEPRC	Изменение с начала года, %
    HIGH	HIGH	Максимум за день
    LOW	LOW	Минимум за день
    VOLTODAY	VOLTODAY	Объем в штуках
    TRADEDATE	TRADEDATE	Дата торгов
    TRADINGSESSION	TRADINGSESSION	Код сессии (утренняя, основная)



    """
    cached_value = cache.get(f"moex_index_value_direct_{index}")
    if cached_value is not None:
        return cached_value
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
            last_price = securities_data

            cache.set(f"moex_index_value_direct_{index}", last_price, 300)
            return last_price

        return None

    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Мосбирже: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        print(f"Ошибка парсинга данных: {e}")
        return None
