import logging
import time
from datetime import datetime

import requests
from django.core.management.base import BaseCommand

from data.functions import return_data_from_year
from trade_bot.settings import ALGOPACK_KEY, client_clickhouse

logger = logging.getLogger(__name__)

import zoneinfo

from tqdm import tqdm


class Command(BaseCommand):
    """
    python3 manage.py download_history --secid gazp --from 2026 --till 2026
    """

    help = "Загрузка исторических данных с 2020 года"

    def add_arguments(self, parser):

        parser.add_argument(
            "--secid",
            type=str,
            help="идентификатор инструменты secid",
        )

        parser.add_argument(
            "--from",
            type=str,
            help="Дата начала периода (YYYY-MM-DD)",
        )

        parser.add_argument(
            "--till",
            type=str,
            help="Дата окончания периода (YYYY-MM-DD)",
        )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Загрузка данных!"))
        payload = {}
        headers = {
            "Accept": "application/json",
            "Authorization": ALGOPACK_KEY,
        }
        moscow_tz = zoneinfo.ZoneInfo("Europe/Moscow")
        secid = kwargs["secid"].upper()
        _from = kwargs["from"]
        _till = kwargs["till"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Загрузка данных тикер {secid}, временной промежуток с {_from} по {_till}!"
            )
        )
        error = []
        for year in range(int(_from), int(_till) + 1, 1):
            day_from_year = return_data_from_year(year)

            for day in tqdm(day_from_year, desc="download..."):
                time.sleep(1)
                url = f"https://apim.moex.com/iss/datashop/algopack/eq/tradestats/{secid}.json?from={day}&till={day}"

                try:
                    response = requests.request(
                        "GET", url, headers=headers, data=payload, timeout=30
                    )
                except Exception:
                    logger.warning(
                        f"Ошибка загрузки данных request:  {response}"
                    )
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
                        client_clickhouse.execute(
                            "INSERT INTO test_trade.test_tradestats VALUES",
                            data_rows,
                        )
                    except Exception as e:
                        print(f"Encountered an error: {e}")
                        logger.warning(
                            f"Encountered an error: {e}, ошибка загрузки данных {data_rows}"
                        )
                else:
                    pass
        client_clickhouse.drop_duplicated("test_trade", "test_tradestats")
        self.stdout.write(self.style.SUCCESS("Дубликаты удалены!"))
