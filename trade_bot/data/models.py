from django.db import models


class TradeData(models.Model):
    """
    TradeStats
    https://apim.moex.com/iss/datashop/algopack/eq/tradestats/
    """

    # Основные поля с индексами
    tradedate = models.DateField(db_index=True, verbose_name="Дата сделки")
    tradetime = models.TimeField(db_index=True, verbose_name="время сделки")
    secid = models.CharField(
        max_length=36, db_index=True, verbose_name="код инструмента"
    )  # bytes: 36

    # Ценовые данные (double → Decimal для точности)
    pr_open = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="цена открытия",
    )
    pr_high = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="максимальная цена за период",
    )
    pr_low = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="минимальная цена за период",
    )
    pr_close = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="последняя цена за период",
    )
    pr_std = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="стандартное отклонение цены",
    )
    pr_vwap = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="взвешенная средняя цена",
    )
    pr_change = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="изменение цены за период, %",
    )

    # Объемные показатели (int32, int64)
    vol = models.IntegerField(
        null=True, blank=True, verbose_name="объем в лотах"
    )  # int32
    val = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="объем в рублях",
    )  # double
    trades = models.IntegerField(
        null=True, blank=True, verbose_name="количество сделок"
    )  # int32

    # Показатели по покупкам/продажам
    trades_b = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во сделок на покупку"
    )  # int32
    trades_s = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во сделок на покупку"
    )  # int32
    val_b = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="объем покупок в рублях",
    )
    val_s = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="объем продаж в рублях",
    )
    vol_b = models.BigIntegerField(
        null=True, blank=True, verbose_name="объем покупок в лотах"
    )  # int64
    vol_s = models.BigIntegerField(
        null=True, blank=True, verbose_name="объем продаж в лотах"
    )  # int64
    disb = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="соотношение объема покупок и продаж",
    )
    pr_vwap_b = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="средневзвешенная цена покупки",
    )
    pr_vwap_s = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name="средневзвешенная цена продажи",
    )

    # Секундные данные (int32)
    systime = models.DateTimeField(db_index=True, verbose_name="время системы")
    sec_pr_open = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во секунд до pr_open"
    )
    sec_pr_high = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во секунд до pr_high"
    )
    sec_pr_low = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во секунд до pr_low"
    )
    sec_pr_close = models.IntegerField(
        null=True, blank=True, verbose_name="кол-во секунд до pr_close"
    )

    class Meta:
        db_table = "trade_data"
        indexes = [
            models.Index(
                fields=["secid", "tradedate", "tradetime"],
                name="idx_secid_date_time",
            ),
            models.Index(
                fields=["tradedate", "tradetime"], name="idx_date_time"
            ),
            models.Index(fields=["systime"], name="idx_systime"),
        ]
        unique_together = [["secid", "tradedate", "tradetime"]]
        ordering = [["tradedate", "tradetime"]]


from django.db import models


class FinancialInstrument(models.Model):
    """Модель финансового инструмента на основе данных T-Invest API."""

    # Идентификаторы
    uid = models.UUIDField(
        primary_key=True,
        help_text="Уникальный идентификатор инструмента (Tinkoff UID)",
    )
    figi = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        help_text="Financial Instrument Global Identifier",
    )
    ticker = models.CharField(
        max_length=20, db_index=True, help_text="Тикер инструмента"
    )
    class_code = models.CharField(
        max_length=20, help_text="Класс-код (например, TQBR)"
    )

    # Описание
    name = models.CharField(
        max_length=255, help_text="Название компании или инструмента"
    )
    type = models.CharField(
        max_length=50,
        help_text="Тип инструмента (shares, etf, bond, currency, futures)",
    )
    exchange = models.CharField(
        max_length=100, help_text="Биржа проведения торгов"
    )
    currency = models.CharField(
        max_length=10, help_text="Валюта торгов (rub, usd, eur...)"
    )

    # Торговые параметры
    lot = models.PositiveIntegerField(help_text="Размер торгового лота")
    min_price_increment = models.DecimalField(
        max_length=20,
        max_digits=18,
        decimal_places=9,
        help_text="Минимальный шаг цены",
    )
    scale = models.IntegerField(
        help_text="Количество знаков после запятой для цены"
    )
    trading_status = models.CharField(
        max_length=100, help_text="Текущий статус торговли инструментом"
    )

    # Флаги доступности
    api_trade_available_flag = models.BooleanField(
        default=False, help_text="Доступность торговли через API"
    )
    buy_available_flag = models.BooleanField(
        default=False, help_text="Доступность покупки"
    )
    sell_available_flag = models.BooleanField(
        default=False, help_text="Доступность продажи"
    )
    short_enabled_flag = models.BooleanField(
        default=False, help_text="Доступность шорта"
    )

    # Рисковые коэффициенты (маржинальная торговля)
    klong = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        help_text="Коэффициент ставки риска для лонга",
    )
    kshort = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        help_text="Коэффициент ставки риска для шорта",
    )

    # Системные поля Django
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "financial_instruments"
        verbose_name = "Финансовый инструмент"
        verbose_name_plural = "Финансовые инструменты"
        indexes = [
            models.Index(fields=["ticker", "type"]),
        ]

    def __str__(self):
        return f"{self.ticker} - {self.name}"
