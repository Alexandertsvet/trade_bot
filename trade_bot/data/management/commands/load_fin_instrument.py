from django.core.management.base import BaseCommand
from django.utils import timezone
from t_tech.invest import Client, SecurityTradingStatus
from t_tech.invest.services import InstrumentsService
from t_tech.invest.utils import quotation_to_decimal

from data.models import FinancialInstrument
from trade_bot.settings import TINKOFF_TOKEN_SANDBOX


class Command(BaseCommand):
    """
    python3 manage.py load_fin_instrument
    """

    help = "Модель финансового инструмента на основе данных T-Invest API."

    def handle(self, *args, **kwargs):
        fin_instrument = FinancialInstrument.objects.all().count()
        self.stdout.write(
            self.style.SUCCESS(f"Кол-во объектов в базе: {fin_instrument}")
        )
        self.stdout.write("Начало загрузки данных из API...")

        instruments_data = []

        methods = [
            "shares",
            "bonds",
            "etfs",
            "currencies",
            "futures",
        ]
        current_time = timezone.now()

        # Инициализация клиента Tinkoff Инвестиций
        with Client(TINKOFF_TOKEN_SANDBOX) as client:
            instruments_service: InstrumentsService = client.instruments

            for method in methods:
                self.stdout.write(f"Запрос инструментов категории: {method}")

                # Получаем список инструментов через нужный метод API
                api_response = getattr(instruments_service, method)()

                for item in api_response.instruments:
                    # Вычисление scale (защита от AttributeError, если nano отсутствует)
                    nano_val = getattr(item.min_price_increment, "nano", 0)
                    scale = 9 - len(str(nano_val)) + 1

                    # Формируем объект модели Django без сохранения в БД (память)
                    instrument_obj = FinancialInstrument(
                        uid=item.uid,
                        figi=item.figi,
                        ticker=item.ticker,
                        class_code=item.class_code,
                        name=item.name,
                        type=method,
                        exchange=item.exchange,
                        currency=item.currency,
                        lot=item.lot,
                        min_price_increment=quotation_to_decimal(
                            item.min_price_increment
                        ),
                        scale=scale,
                        trading_status=str(
                            SecurityTradingStatus(item.trading_status).name
                        ),
                        api_trade_available_flag=item.api_trade_available_flag,
                        buy_available_flag=item.buy_available_flag,
                        sell_available_flag=item.sell_available_flag,
                        short_enabled_flag=item.short_enabled_flag,
                        klong=quotation_to_decimal(item.klong),
                        kshort=quotation_to_decimal(item.kshort),
                        updated_at=current_time,
                    )
                    instruments_data.append(instrument_obj)

        if not instruments_data:
            self.stdout.write(
                self.style.WARNING("Данные для импорта отсутствуют.")
            )
            return

        self.stdout.write(
            f"Получено {len(instruments_data)} инструментов. Запись в PostgreSQL..."
        )

        # Список полей для обновления в случае совпадения Primary Key (uid)
        fields_to_update = [
            "figi",
            "ticker",
            "class_code",
            "name",
            "type",
            "exchange",
            "currency",
            "lot",
            "min_price_increment",
            "scale",
            "trading_status",
            "api_trade_available_flag",
            "buy_available_flag",
            "sell_available_flag",
            "short_enabled_flag",
            "klong",
            "kshort",
            "updated_at",
        ]

        # Быстрая пакетная вставка (Upsert) средствами Django и PostgreSQL
        FinancialInstrument.objects.bulk_create(
            instruments_data,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=["uid"],
            update_fields=fields_to_update,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Успешно импортировано/обновлено инструментов: {len(instruments_data)}"
            )
        )

        fin_instrument_final = FinancialInstrument.objects.all().count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Кол-во объектов в базе после обновления: {fin_instrument_final}"
            )
        )
