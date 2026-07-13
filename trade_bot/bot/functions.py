import logging
import os
import zoneinfo
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from t_tech.invest import (
    Client,
    RequestError,
)
from tqdm import tqdm

from trade_bot.settings import client_clickhouse
from decimal import Decimal
from typing import Union

from t_tech.invest.schemas import MoneyValue, Quotation
from t_tech.invest.utils import money_to_decimal, quotation_to_decimal

logger = logging.getLogger(__name__)


load_dotenv()
Authorization = os.getenv("Authorization")
headers = {
    "Accept": "application/json",
    "Authorization": Authorization,
}
payload = {}
moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")


def insert_data(data_rows):
    if data_rows:
        for row in data_rows:
            row[1] = datetime.strptime(
                f"{row[0]} {row[1]}", "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=moscow_tz)
            row[0] = datetime.strptime(row[0], "%Y-%m-%d").replace(
                tzinfo=moscow_tz
            )

            row[22] = datetime.strptime(row[22], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=moscow_tz
            )
        try:
            client_clickhouse.execute(
                "INSERT INTO test_trade.test_tradestats VALUES", data_rows
            )
        except Exception as e:
            logger.warning(
                f"Encountered an error: {e}, ошибка загрузки данных {data_rows}"
            )
    else:
        logger.warning(f"Ошибка загрузки данных {data_rows}")


def real_time_data(headers):
    url = "https://apim.moex.com/iss/datashop/algopack/eq/tradestats/GAZP.json?latest=1"

    payload = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    if response.status_code == 200:
        data = response.json().get("data", {}).get("data", {})
        if data:
            date = data[0][:2]
        return response.status_code, data, date
    data = None
    date = None
    return response.status_code, data, date


def receive_and_save(headers):
    last_time_from_db = client_clickhouse.get_last_time(secid="GAZP")
    dt_object = last_time_from_db[0][0]
    last_time = [
        dt_object.strftime("%Y-%m-%d"),
        dt_object.strftime("%H:%M:%S"),
    ]
    status_code, data, date = real_time_data(headers)
    if status_code == 200 and last_time != date:
        insert_data(data)
        logger.info(f"Обновление базы данных {data}")
        last_time = date
        return True
    else:
        logger.info(
            f"Получен ответ сервера {status_code}, данные в базе актуальны."
        )
        return False


def get_quantity_all(account, target):
    try:
        with Client(account.access_token, target=target) as client:
            response = client.users.get_accounts()
            for account in response.accounts:
                portfolio = client.operations.get_portfolio(
                    account_id=account.id
                )
                if len(portfolio.positions) == 2:
                    return portfolio.positions[1].quantity_lots.units
                else:
                    return 0
    except RequestError as e:
        logger.error(
            f"Ошибка API T-Invest: {e.details if e.details else 'Неверные параметры или токен'}"
        )
        logger.error(
            f"Ошибка API: {e.metadata.message if e.metadata else str(e)}"
        )
        return redirect("user:sandbox_detail", pk=account.pk)
    except Exception as e:
        logger.error(f"Критическая ошибка подключения: {e}")


def return_curent_last_day():
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    return (yesterday_str, today_str)


def update_data(client, headers):
    for day in tqdm(return_curent_last_day(), desc="download..."):
        secid = "GAZP"
        url = f"https://apim.moex.com/iss/datashop/algopack/eq/tradestats/{secid}.json?from={day}&till={day}"
        try:
            response = requests.request(
                "GET", url, headers=headers, data=payload, timeout=30
            )
        except Exception:
            logging.warning(f"Ошибка загрузки данных request:  {response}")
            time.sleep(10)
            response = requests.request(
                "GET", url, headers=headers, data=payload, timeout=30
            )

        data = response.json().get("data", {})
        metadata = data.get("metadata", {})
        columns = data.get("columns", {})
        data_rows = data.get("data", {})
        if data_rows:
            for row in data_rows:
                row[1] = datetime.strptime(
                    f"{row[0]} {row[1]}", "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=moscow_tz)
                row[0] = datetime.strptime(row[0], "%Y-%m-%d").replace(
                    tzinfo=moscow_tz
                )

                row[22] = datetime.strptime(
                    row[22], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=moscow_tz)
            try:
                client.execute(
                    "INSERT INTO test_trade.test_tradestats VALUES", data_rows
                )
            except Exception as e:
                print(f"Encountered an error: {e}")
                logging.warning(
                    f"Encountered an error: {e}, ошибка загрузки данных {data_rows}"
                )

        else:
            pass

def cast_to_decimal(value: Union[MoneyValue, Quotation, None]) -> Decimal:
    """Универсальная функция для безопасной конвертации.

    Принимает MoneyValue, Quotation или None, возвращает Decimal.
    """
    if value is None:
        return Decimal("0.0")

    if isinstance(value, MoneyValue):
        return money_to_decimal(value)

    if isinstance(value, Quotation):
        return quotation_to_decimal(value)

    # Защита на случай, если передали некорректный тип данных
    raise TypeError(
        f"Ожидался тип MoneyValue, Quotation или None. Получен: {type(value)}"
    )
