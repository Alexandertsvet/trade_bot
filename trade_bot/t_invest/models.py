import uuid

from django.conf import settings
from django.db import models
from encrypted_fields.fields import EncryptedCharField
from t_tech.invest import (
    OrderDirection as TTechDirection,
    OrderDirection as TTechOrderDirection,
    OrderExecutionReportStatus as TTechStatus,
    OrderType as TTechOrderType,
    PriceType as TTechPriceType,
    TimeInForceType as TTechTimeInForceType,
)
from t_tech.invest.utils import quotation_to_decimal, money_to_decimal
from t_tech.invest.schemas import (
    MoneyValue,
    Quotation,
)

from data.models import FinancialInstrument


class TinkoffAccaunt(models.Model):
    """Реальные торговые аккаунты.
    Токен с доступом к конкретному счету — токен для получения доступа
    только к одному конкретному счету пользователя.
    Уровень прав доступа (readonly, full-access) также можно настроить.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="real_accounts",
    )
    account_id = models.CharField(max_length=50, unique=True)
    access_token = EncryptedCharField(
        max_length=255,
        help_text="api key токен с доступом к конкретному счету T инвестиции",
    )
    access_token_algopack = EncryptedCharField(
        max_length=1600, help_text="api key algopack"
    )
    description = models.CharField(
        max_length=255, blank=True, help_text="Краткое описание..."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Account: {self.account_id}"


class FavoriteInstrument(models.Model):
    """Модель избранных финансовых инструментов пользователя."""

    user = models.ForeignKey(
        TinkoffAccaunt,
        on_delete=models.CASCADE,
        related_name="favorite_instruments",
        verbose_name="Пользователь",
    )
    instrument = models.ForeignKey(
        FinancialInstrument,
        on_delete=models.CASCADE,
        related_name="favorited_by_accaunt",
        verbose_name="Финансовый инструмент",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата добавления"
    )

    class Meta:
        db_table = "favorite_instruments"
        verbose_name = "Избранный инструмент"
        verbose_name_plural = "Избранные инструменты"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "instrument"], name="unique_user_instrument"
            )
        ]

    def __str__(self):
        return f"{self.user} -> {self.instrument.ticker}"


class Portfolio(models.Model):
    """Основная модель для хранения состояния портфеля."""

    account = models.OneToOneField(
        TinkoffAccaunt,
        to_field="account_id",
        on_delete=models.CASCADE,
        related_name="portfolio",
        db_column="account_id",
    )
    # account_id='354d58c4-e658-492b-ab47-5958c3af7b25',
    total_amount_shares = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость акций (значение)",
    )
    total_amount_bonds = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость облигаций (значение)",
    )
    total_amount_etf = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость ETF (значение)",
    )
    total_amount_currencies = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость валюты (значение)",
    )
    total_amount_futures = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость фьючерсов (значение)",
    )
    total_amount_options = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость опционов (значение)",
    )
    total_amount_sp = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость структ. продуктов (значение)",
    )
    total_amount_portfolio = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Общая стоимость портфеля (значение)",
    )
    total_amount_dfa = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Стоимость ЦФА (значение)",
    )
    # Показатели доходности портфеля
    expected_yield = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Ожидаемая доходность"
    )
    daily_yield = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Дневная доходность (значение)",
    )
    daily_yield_relative = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Относительная дневная доходность",
    )
    # Списки и метаданные
    virtual_positions = models.JSONField(
        default=list, blank=True, verbose_name="Виртуальные позиции"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Дата обновления данных"
    )

    class Meta:
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"

    def __str__(self):
        return f"Портфель {self.account_id} ({self.total_amount_portfolio})"


class PortfolioPosition(models.Model):
    """Модель для хранения позиций внутри конкретного портфеля."""

    # Связь "один ко многим" с моделью портфеля
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Позиции портфеля",
    )
    instrument = models.ForeignKey(
        FinancialInstrument,
        on_delete=models.PROTECT,  # PROTECT не позволит удалить инструмент, пока он есть в чьем-либо портфеле
        related_name="portfolio_positions",
        db_column="instrument_uid",  # Явно сохраняем UUID в колонку instrument_uid
        verbose_name="Финансовый инструмент",
    )

    # Идентификаторы инструмента
    # figi = models.CharField(max_length=20, verbose_name="FIGI")
    # ticker = models.CharField(max_length=20, blank=True, verbose_name="Тикер")
    # instrument_type = models.CharField(max_length=50, verbose_name="Тип инструмента")
    # instrument_uid = models.UUIDField(verbose_name="UID инструмента")

    position_uid = models.UUIDField(verbose_name="UID позиции")
    # Количественные параметры (в Decimal)
    quantity = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Количество бумаг"
    )
    quantity_lots = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Количество лотов"
    )
    blocked = models.BooleanField(default=False, verbose_name="Заблокировано")
    blocked_lots = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Заблокировано лотов"
    )

    # Стоимостные параметры позиции
    average_position_price = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Средняя цена позиции"
    )
    current_price = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Текущая цена"
    )
    average_position_price_fifo = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Средняя цена по FIFO"
    )

    # Доходность и маржинальные показатели позиции
    expected_yield = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Ожидаемая доходность"
    )
    expected_yield_fifo = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        verbose_name="Ожидаемая доходность по FIFO",
    )
    daily_yield = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Дневная доходность"
    )
    current_nkd = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Текущий НКД"
    )

    average_position_price_pt = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Средняя цена в пунктах"
    )
    var_margin = models.DecimalField(
        max_digits=18, decimal_places=9, verbose_name="Вариационная маржа"
    )

    class Meta:
        verbose_name = "Позиция"
        verbose_name_plural = "Позиции"
        # Защита от дублей одного и того же инструмента в рамках одной выгрузки портфеля
        unique_together = ("portfolio", "position_uid")

    @property
    def total_position_current_price(self):
        """Возвращает полную стоимость позиции по текущей цене"""
        if self.quantity and self.current_price:
            return self.quantity * self.current_price
        return 0

    @property
    def total_position_profit_or_loss(self):
        """Возвращает текущую прибыль или убыток по позиции"""
        if (
            self.quantity
            and self.current_price
            and self.average_position_price
        ):
            return self.quantity * (
                self.current_price - self.average_position_price
            )
        return 0

    def __str__(self):
        return f"{self.instrument.ticker or self.instrument.figi} — {self.quantity} шт."


# ============================================================================================


class SandboxPostOrderRequest(models.Model):
    """
    ORDER_DIRECTION_UNSPECIFIED	0	Значение не указано
    ORDER_DIRECTION_BUY	1	Покупка
    ORDER_DIRECTION_SELL	2	Продажа
    """

    class OrderDirection(models.IntegerChoices):
        ORDER_DIRECTION_UNSPECIFIED = (
            TTechOrderDirection.ORDER_DIRECTION_UNSPECIFIED.value,
            "Значение не указано",
        )
        ORDER_DIRECTION_BUY = (
            TTechOrderDirection.ORDER_DIRECTION_BUY.value,
            "Покупка",
        )
        ORDER_DIRECTION_SELL = (
            TTechOrderDirection.ORDER_DIRECTION_SELL.value,
            "Продажа",
        )

    """
    ORDER_TYPE_UNSPECIFIED	0	Значение не указано
    ORDER_TYPE_LIMIT	1	Лимитная
    ORDER_TYPE_MARKET	2	Рыночная
    ORDER_TYPE_BESTPRICE	3	Лучшая цена
    """

    class OrderType(models.IntegerChoices):
        ORDER_TYPE_UNSPECIFIED = (
            TTechOrderType.ORDER_TYPE_UNSPECIFIED.value,
            "Значение не указано",
        )
        ORDER_TYPE_LIMIT = TTechOrderType.ORDER_TYPE_LIMIT.value, "Лимитная"
        ORDER_TYPE_MARKET = TTechOrderType.ORDER_TYPE_MARKET.value, "Рыночная"
        ORDER_TYPE_BESTPRICE = (
            TTechOrderType.ORDER_TYPE_BESTPRICE.value,
            "Лучшая цена",
        )

    """
    TIME_IN_FORCE_UNSPECIFIED	0	Значение не определено см. TIME_IN_FORCE_DAY
    TIME_IN_FORCE_DAY	1	Заявка действует до конца торгового дня. Значение по умолчанию
    TIME_IN_FORCE_FILL_AND_KILL	2	Если в момент выставления возможно исполнение заявки(в т.ч. частичное), 
    заявка будет исполнена или отменена сразу после выставления
    TIME_IN_FORCE_FILL_OR_KILL	3	Если в момент выставления возможно полное исполнение заявки,
    заявка будет исполнена или отменена сразу после выставления, недоступно для срочного рынка и торговли по выходным
    """

    class TimeInForceType(models.IntegerChoices):
        TIME_IN_FORCE_UNSPECIFIED = (
            TTechTimeInForceType.TIME_IN_FORCE_UNSPECIFIED.value,
            "Значение не определено",
        )
        TIME_IN_FORCE_DAY = (
            TTechTimeInForceType.TIME_IN_FORCE_DAY.value,
            "Заявка действует до конца торгового дня",
        )
        TIME_IN_FORCE_FILL_AND_KILL = (
            TTechTimeInForceType.TIME_IN_FORCE_FILL_AND_KILL.value,
            "Исполнить или отменить (частично)",
        )
        TIME_IN_FORCE_FILL_OR_KILL = (
            TTechTimeInForceType.TIME_IN_FORCE_FILL_OR_KILL.value,
            "Исполнить полностью или отменить",
        )

    """
    PRICE_TYPE_UNSPECIFIED	0	Значение не определено
    PRICE_TYPE_POINT	1	Цена в пунктах (только для фьючерсов и облигаций)
    PRICE_TYPE_CURRENCY	2	Цена в валюте расчетов по инструменту
    """

    class PriceType(models.IntegerChoices):
        PRICE_TYPE_UNSPECIFIED = (
            TTechPriceType.PRICE_TYPE_UNSPECIFIED.value,
            "Значение не определено",
        )
        PRICE_TYPE_POINT = (
            TTechPriceType.PRICE_TYPE_POINT.value,
            "Цена в пунктах (для фьючерсов и облигаций)",
        )
        PRICE_TYPE_CURRENCY = (
            TTechPriceType.PRICE_TYPE_CURRENCY.value,
            "Цена в валюте расчетов по инструменту",
        )

    account_id = models.ForeignKey(
        TinkoffAccaunt,
        to_field="account_id",
        on_delete=models.CASCADE,
        related_name="post_order_request",
    )

    instrument_id = models.ForeignKey(
        "data.FinancialInstrument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="uid",
        db_column="instrument_uid",
        related_name="postorder_by_instrument",
        help_text="Связь с инструментом по instrument_uid",
    )
    quantity = models.BigIntegerField(help_text="Количество лотов.")
    price = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        blank=True,
        null=True,
        help_text="Цена за 1 инструмент. Игнорируется для рыночных поручений.",
    )
    direction = models.IntegerField(
        choices=OrderDirection.choices,
        help_text="Направление операции (BUY/SELL).",
    )
    order_type = models.IntegerField(
        choices=OrderType.choices, help_text="Тип заявки (LIMIT/MARKET)."
    )
    time_in_force = models.IntegerField(
        choices=TimeInForceType.choices,
        default=TimeInForceType.TIME_IN_FORCE_DAY,
        help_text="Алгоритм исполнения поручения (применяется к лимитным).",
    )
    price_type = models.IntegerField(
        choices=PriceType.choices,
        default=PriceType.PRICE_TYPE_UNSPECIFIED,
        help_text="Тип цены.",
    )
    confirm_margin_trade = models.BooleanField(
        default=False,
        help_text="Согласие на выставление заявки, которая может привести к непокрытой позиции.",
    )
    order_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Идентификатор запроса выставления поручения для целей идемпотентности.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Поручение"
        verbose_name_plural = "Поручения"
        indexes = [
            models.Index(fields=["account_id"]),
            models.Index(fields=["instrument_id"]),
        ]

    def __str__(self):
        return f"Order {self.order_id} - {self.direction} {self.instrument_id}"

    def to_sdk_args(self) -> dict:
        """
        Преобразует модель Django в словарь аргументов для SDK t_tech.invest.
        """
        sdk_price = None
        if self.price is not None:
            units = int(self.price)
            nano = int((self.price - units) * 1_000_000_000)
            sdk_price = Quotation(units=units, nano=nano)

        return {
            "account_id": self.account_id.account_id,
            "instrument_id": (
                str(self.instrument_id_id) if self.instrument_id_id else ""
            ),
            "quantity": self.quantity,
            "price": sdk_price,
            "direction": TTechOrderDirection(self.direction),
            "order_type": TTechOrderType(self.order_type),
            "time_in_force": TTechTimeInForceType(self.time_in_force),
            "price_type": TTechPriceType(self.price_type),
            "order_id": str(self.order_id),
        }


from t_tech.invest import OrderType as TTechOrderType


class SandboxPostOrderResponse(models.Model):
    # --- Django Choices (на базе официальных Enum из SDK) ---
    class ExecutionReportStatus(models.IntegerChoices):
        EXECUTION_REPORT_STATUS_UNSPECIFIED = (
            TTechStatus.EXECUTION_REPORT_STATUS_UNSPECIFIED.value,
            "Не определен",
        )
        EXECUTION_REPORT_STATUS_PARTIALLYFILL = (
            TTechStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL.value,
            "Исполнен частично",
        )
        EXECUTION_REPORT_STATUS_FILL = (
            TTechStatus.EXECUTION_REPORT_STATUS_FILL.value,
            "Исполнен полностью",
        )
        EXECUTION_REPORT_STATUS_CANCELLED = (
            TTechStatus.EXECUTION_REPORT_STATUS_CANCELLED.value,
            "Отменен",
        )
        EXECUTION_REPORT_STATUS_NEW = (
            TTechStatus.EXECUTION_REPORT_STATUS_NEW.value,
            "Новый / Выставлен",
        )
        EXECUTION_REPORT_STATUS_REJECTED = (
            TTechStatus.EXECUTION_REPORT_STATUS_REJECTED.value,
            "Отклонен",
        )

    class OrderDirection(models.IntegerChoices):
        ORDER_DIRECTION_UNSPECIFIED = (
            TTechDirection.ORDER_DIRECTION_UNSPECIFIED.value,
            "Значение не указано",
        )
        ORDER_DIRECTION_BUY = (
            TTechDirection.ORDER_DIRECTION_BUY.value,
            "Покупка",
        )
        ORDER_DIRECTION_SELL = (
            TTechDirection.ORDER_DIRECTION_SELL.value,
            "Продажа",
        )

    class OrderType(models.IntegerChoices):
        ORDER_TYPE_UNSPECIFIED = (
            TTechOrderType.ORDER_TYPE_UNSPECIFIED.value,
            "Значение не указано",
        )
        ORDER_TYPE_LIMIT = TTechOrderType.ORDER_TYPE_LIMIT.value, "Лимитная"
        ORDER_TYPE_MARKET = TTechOrderType.ORDER_TYPE_MARKET.value, "Рыночная"
        ORDER_TYPE_BESTPRICE = (
            TTechOrderType.ORDER_TYPE_BESTPRICE.value,
            "Лучшая цена",
        )

    order_response = models.OneToOneField(
        "SandboxPostOrderRequest",  # Имя вашей первой модели
        on_delete=models.CASCADE,  # При удалении запроса удалится и ответ
        related_name="response_log",  # Позволит делать так: request_instance.response_log
        help_text="Ссылка на исходный запрос поручения",
    )

    # --- Идентификаторы ---
    order_id = models.UUIDField(
        unique=True,
        help_text="Биржевой идентификатор заявки, присвоенный Тинькофф.",
    )
    order_request_id = models.UUIDField(
        blank=True,
        null=True,
        help_text="Идентификатор изначального запроса (UUID для идемпотентности).",
    )
    instrument_uid = models.UUIDField(
        blank=True, null=True, help_text="UID финансового инструмента."
    )
    figi = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="FIGI-идентификатор инструмента.",
    )

    # --- Статусы и Объемы ---
    execution_report_status = models.IntegerField(
        choices=ExecutionReportStatus.choices,
        default=ExecutionReportStatus.EXECUTION_REPORT_STATUS_UNSPECIFIED,
        help_text="Текущий статус («стаканного» исполнения) заявки.",
    )
    direction = models.IntegerField(
        choices=OrderDirection.choices,
        default=OrderDirection.ORDER_DIRECTION_UNSPECIFIED,
        help_text="Направление операции.",
    )
    order_type = models.IntegerField(
        choices=OrderType.choices,
        default=OrderType.ORDER_TYPE_UNSPECIFIED,
        help_text="Тип заявки.",
    )
    lots_requested = models.BigIntegerField(help_text="Запрошено лотов.")
    lots_executed = models.BigIntegerField(
        help_text="Фактически исполнено лотов."
    )

    # --- Финансовые поля (MoneyValue / Quotation преобразованные в Decimal) ---
    # max_digits=18 и decimal_places=9 идеально подходят под формат SDK (units + nano)
    initial_order_price = models.DecimalField(
        max_digits=18, decimal_places=9, help_text="Начальная цена заявки."
    )
    executed_order_price = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        help_text="Средняя цена исполнившихся лотов.",
    )
    total_order_amount = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        help_text="Общая стоимость по заявке (с комиссией).",
    )
    initial_commission = models.DecimalField(
        max_digits=18, decimal_places=9, help_text="Предварительная комиссия."
    )
    executed_commission = models.DecimalField(
        max_digits=18, decimal_places=9, help_text="Фактическая комиссия."
    )
    aci_value = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        help_text="Накопленный купонный доход (НКД).",
    )
    initial_security_price = models.DecimalField(
        max_digits=18, decimal_places=9, help_text="Начальная цена бумаги."
    )
    initial_order_price_pt = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        help_text="Начальная цена заявки в пунктах (для облигаций).",
    )

    # --- Логи и Служебная информация ---
    message = models.TextField(
        blank=True,
        default="",
        help_text="Дополнительное сообщение от торговой системы / текст ошибки.",
    )
    response_metadata = models.TextField(
        blank=True,
        default="",
        help_text="Сырые метаданные ответа брокера (tracking_id, server_time).",
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Время сохранения ответа в вашу БД."
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Время изменения."
    )

    class Meta:
        verbose_name = "Ответ на ордер (Песочница)"
        verbose_name_plural = "Ответы на ордера (Песочница)"
        # Индексы для быстрой выборки ответов по конкретной акции или заявке
        indexes = [
            models.Index(fields=["order_id"]),
            models.Index(fields=["instrument_uid"]),
            models.Index(fields=["order_request_id"]),
        ]

    def __str__(self):
        return f"Response {self.order_id} - Status: {self.execution_report_status}"
