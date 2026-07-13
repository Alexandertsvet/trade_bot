import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from t_tech.invest import Client, InstrumentIdType, SecurityTradingStatus
from t_tech.invest.services import InstrumentsService
from t_tech.invest.utils import quotation_to_decimal

from data.models import FinancialInstrument
from t_invest.models import Portfolio, PortfolioPosition, TinkoffAccaunt

from decimal import Decimal
from typing import Union

from t_tech.invest.schemas import MoneyValue, Quotation
from t_tech.invest.utils import money_to_decimal, quotation_to_decimal

logger = logging.getLogger(__name__)


def get_instrument_by_uid(uid, TOKEN):
    with Client(TOKEN, target=settings.TARGET_TRADE) as client:
        instruments: InstrumentsService = client.instruments
        try:
            instrument = instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID, id=uid
            ).instrument
        except Exception:
            logger.exception(
                f"Ошибка получение параметров интсрумента по uid. {uid}"
            )
        return instrument


def cast_to_decimal(obj) -> Decimal:
    """Конвертирует объекты MoneyValue и Quotation из SDK в Python Decimal."""
    if not obj:
        return Decimal("0.0")
    # Формула нормализации: units + (nano / 10^9)
    return Decimal(obj.units) + Decimal(obj.nano) / Decimal("1000000000")


def save_tinkoff_portfolio(
    account_id: str, token, portfolio_data
) -> Portfolio:
    """Парсит ответ PortfolioResponse от Tinkoff API и сохраняет его в БД Django.

    :param account_id: Строковый ID аккаунта (UUID).
    :param portfolio_data: Объект PortfolioResponse, полученный из SDK.
    """
    # 1. Проверяем, существует ли аккаунт в нашей базе данных
    try:
        account = TinkoffAccaunt.objects.get(account_id=account_id)
    except TinkoffAccaunt.DoesNotExist:
        logger.exception("Произошла ошибка, аккаунт не найден.")
        raise ValueError(f"Аккаунт с ID {account_id} не найден в базе данных.")

    # Используем атомарную транзакцию, чтобы при любой ошибке база не обновилась частично
    with transaction.atomic():
        # 2. Обновляем или создаем основную запись портфеля
        portfolio, created = Portfolio.objects.update_or_create(
            account=account,
            defaults={
                "total_amount_shares": cast_to_decimal(
                    portfolio_data.total_amount_shares
                ),
                "total_amount_bonds": cast_to_decimal(
                    portfolio_data.total_amount_bonds
                ),
                "total_amount_etf": cast_to_decimal(
                    portfolio_data.total_amount_etf
                ),
                "total_amount_currencies": cast_to_decimal(
                    portfolio_data.total_amount_currencies
                ),
                "total_amount_futures": cast_to_decimal(
                    portfolio_data.total_amount_futures
                ),
                "total_amount_options": cast_to_decimal(
                    portfolio_data.total_amount_options
                ),
                "total_amount_sp": cast_to_decimal(
                    portfolio_data.total_amount_sp
                ),
                "total_amount_portfolio": cast_to_decimal(
                    portfolio_data.total_amount_portfolio
                ),
                "total_amount_dfa": cast_to_decimal(
                    portfolio_data.total_amount_dfa
                ),
                "expected_yield": cast_to_decimal(
                    portfolio_data.expected_yield
                ),
                "daily_yield": cast_to_decimal(portfolio_data.daily_yield),
                "daily_yield_relative": cast_to_decimal(
                    portfolio_data.daily_yield_relative
                ),
                "virtual_positions": getattr(
                    portfolio_data, "virtual_positions", []
                ),
            },
        )

        # 3. Удаляем старые позиции этого портфеля, чтобы перезаписать актуальный срез
        portfolio.positions.all().delete()

        # 4. Формируем список новых позиций для пакетной вставки (bulk_create)
        positions_to_create = []

        for pos in portfolio_data.positions:
            # Находим инструмент в глобальном справочнике по его UID
            try:
                if FinancialInstrument.objects.filter(
                    uid=pos.instrument_uid
                ).exists():
                    instrument = FinancialInstrument.objects.get(
                        uid=pos.instrument_uid
                    )
                else:
                    # Добавим инструмент в базу.
                    instrurument_data = get_instrument_by_uid(
                        pos.instrument_uid, token
                    )

                    # Вычисление scale (защита от AttributeError, если nano отсутствует)
                    current_time = timezone.now()
                    nano_val = getattr(
                        instrurument_data.min_price_increment, "nano", 0
                    )
                    scale = 9 - len(str(nano_val)) + 1
                    instrument, created = (
                        FinancialInstrument.objects.get_or_create(
                            uid=instrurument_data.uid,
                            figi=instrurument_data.figi,
                            ticker=instrurument_data.ticker,
                            class_code=instrurument_data.class_code,
                            name=instrurument_data.name,
                            type=instrurument_data.instrument_type,
                            exchange=instrurument_data.exchange,
                            currency=instrurument_data.currency,
                            lot=instrurument_data.lot,
                            min_price_increment=quotation_to_decimal(
                                instrurument_data.min_price_increment
                            ),
                            scale=scale,
                            trading_status=str(
                                SecurityTradingStatus(
                                    instrurument_data.trading_status
                                ).name
                            ),
                            api_trade_available_flag=instrurument_data.api_trade_available_flag,
                            buy_available_flag=instrurument_data.buy_available_flag,
                            sell_available_flag=instrurument_data.sell_available_flag,
                            short_enabled_flag=instrurument_data.short_enabled_flag,
                            klong=quotation_to_decimal(
                                instrurument_data.klong
                            ),
                            kshort=quotation_to_decimal(
                                instrurument_data.kshort
                            ),
                            updated_at=current_time,
                        )
                    )
            except FinancialInstrument.DoesNotExist:
                logger.exception(
                    f"Произошла ошибка, попытка извлечь данных "
                    f"из модели FinancialInstrument, "
                    f"такого uid {pos.instrument_uid} нет в базе."
                )
            # Инициализируем объект модели без сохранения в БД
            position_obj = PortfolioPosition(
                portfolio=portfolio,
                instrument=instrument,
                position_uid=pos.position_uid,
                quantity=cast_to_decimal(pos.quantity),
                quantity_lots=cast_to_decimal(pos.quantity_lots),
                blocked=pos.blocked,
                blocked_lots=cast_to_decimal(pos.blocked_lots),
                average_position_price=cast_to_decimal(
                    pos.average_position_price
                ),
                current_price=cast_to_decimal(pos.current_price),
                average_position_price_fifo=cast_to_decimal(
                    pos.average_position_price_fifo
                ),
                expected_yield=cast_to_decimal(pos.expected_yield),
                expected_yield_fifo=cast_to_decimal(pos.expected_yield_fifo),
                daily_yield=cast_to_decimal(pos.daily_yield),
                current_nkd=cast_to_decimal(pos.current_nkd),
                average_position_price_pt=cast_to_decimal(
                    pos.average_position_price_pt
                ),
                var_margin=cast_to_decimal(pos.var_margin),
            )
            positions_to_create.append(position_obj)

        # Пакетное сохранение всех позиций одним SQL-запросом
        if positions_to_create:
            PortfolioPosition.objects.bulk_create(positions_to_create)

    return portfolio


def datetime_to_unix(time):
    dt_obj = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    unix_timestamp = int(dt_obj.timestamp())
    return unix_timestamp

