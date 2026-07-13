from django.core.management.base import BaseCommand

from data.functions import create_db
from trade_bot.settings import client_clickhouse


class Command(BaseCommand):
    """
    python3 manage.py create_db
    """

    help = "Создание базы данных"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Создание базы данных!"))
        create_db(
            client=client_clickhouse,
            db_name="test_trade",
            table_name="test_tradestats",
        )
        self.stdout.write(
            self.style.SUCCESS("База создана или уже существует!")
        )
