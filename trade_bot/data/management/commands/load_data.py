from decimal import Decimal

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from data.functions import return_data_from_year, return_two_element
from data.models import TradeData
from trade_bot.settings import ALGOPACK_KEY


def convert_value(value, data_type):
    """Конвертация значений в соответствии с типом"""
    if value is None or value == "":
        return None

    if data_type == "double":
        return Decimal(str(value))
    elif data_type in ["int32", "int64"]:
        return int(value)
    elif data_type == "date":
        from datetime import datetime

        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        return value
    elif data_type == "time":
        if isinstance(value, str):
            return value
        return value
    elif data_type == "datetime":
        return value
    else:
        return str(value)


class Command(BaseCommand):
    """
    python3 manage.py load_data --secid gazp --from 2020 --till 2025
    """

    help = "Загружает данные из JSON в базу данных"

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
        # Пример загрузки из JSON-файла

        payload = {}
        headers = {
            "Accept": "application/json",
            "Authorization": ALGOPACK_KEY,
        }

        secid = kwargs["secid"].upper()
        _from = kwargs["from"]
        _till = kwargs["till"]

        for year in range(int(_from), int(_till) + 1, 1):
            day_from_year = return_data_from_year(year)
            two_day = return_two_element(day_from_year)

            for first, next in tqdm(two_day, desc="download..."):
                url = f"https://apim.moex.com/iss/datashop/algopack/eq/tradestats/{secid}.json?from={first}&till={next}"
                response = requests.request(
                    "GET", url, headers=headers, data=payload
                )
                data = response.json().get("data", {})
                metadata = data.get("metadata", {})
                columns = data.get("columns", {})
                data_rows = data.get("data", {})

                objects = []
                for row in data_rows:
                    row_data = {}
                    for idx, col in enumerate(columns):
                        value = row[idx]
                        col_type = metadata[col]["type"]
                        row_data[col] = convert_value(value, col_type)

                    if "SYSTIME" in row_data and row_data["SYSTIME"]:
                        row_data["systime"] = row_data.pop("SYSTIME")

                        """date_str = row_data['systime']
                        # Превращаем строку в объект
                        dt_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        # Делаем объект "aware" (с учетом временной зоны Django)
                        moscow_tz = zoneinfo.ZoneInfo('Europe/Moscow')
                        dt_obj = timezone.make_aware(dt_obj, moscow_tz )
                        row_data['systime'] = dt_obj"""

                    obj = TradeData(**row_data)
                    objects.append(obj)

                with transaction.atomic():
                    TradeData.objects.bulk_create(
                        objects,
                        ignore_conflicts=True,
                    )

        """with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            for item in data:
                # Создаем объект в базе данных
                TradeData.objects.get_or_create(
                    name=item['name'],
                    defaults={'description': item.get('description', '')}
                )"""

        self.stdout.write(
            self.style.SUCCESS(
                f"Данные успешно загружены! {secid}, c {_from} по {_till}"
            )
        )
