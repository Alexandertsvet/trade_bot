from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from user.models import SandboxMoney, TinkoffSandboxAccount


@receiver(post_save, sender=TinkoffSandboxAccount)
def initialize_sandbox_account_assets(sender, instance, created, **kwargs):
    """Автоматически инициализирует базовые валюты при создании аккаунта."""
    if created:
        # Список базовых валют для инициализации кошелька
        default_currencies = ["rub", "usd", "eur"]
        print("signal init")

        currency = "rub"

        SandboxMoney.objects.create(
            account=instance,
            currency=currency,
            balance=Decimal("100000.0"),
            blocked=Decimal("0.0"),
        )
