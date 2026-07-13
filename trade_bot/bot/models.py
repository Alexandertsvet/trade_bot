from django.db import models

from data.models import FinancialInstrument


class BotConfiguration(models.Model):
    name = models.CharField(max_length=50, default="Основной бот")
    instrument = models.ForeignKey(
        FinancialInstrument,
        on_delete=models.PROTECT,
        related_name="bot_instrument",
        db_column="instrument_uid",
        verbose_name="Финансовый инструмент",
    )
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_available_trade(self):
        """Доступность торговли через api (купить/продать)"""
        if (
            self.instrument.api_trade_available_flag
            and self.instrument.buy_available_flag
            and self.instrument.sell_available_flag
        ):
            return True
        return False

    def __str__(self):
        return f"{self.name} ({self.instrument}) - {'Активен' if self.is_active else 'Выключен'}"
