from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from encrypted_fields.fields import EncryptedCharField

from user.constant import MAX_LENGHT_EMAIL, MAX_LENGHT_USERS


class User(AbstractUser):
    email = models.EmailField(
        verbose_name="e-mail",
        unique=True,
        max_length=MAX_LENGHT_EMAIL,
    )
    username = models.CharField(
        unique=True,
        verbose_name="имя пользователя в системе",
        max_length=MAX_LENGHT_USERS,
        validators=[
            RegexValidator(
                regex=r"^[\w.@+-]+$",
                message="«Нельзя использовать пробел и символы, кроме . @ + - _».",
            ),
        ],
    )

    class Meta:
        verbose_name = "Пользователь."
        verbose_name_plural = "Пользователи."

    def clean(self):
        # Если это попытка создания (нет pk) и в базе уже есть хоть один юзер
        if not self.pk and User.objects.exists():
            raise ValidationError(
                "В этой системе может существовать только один пользователь."
            )
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()  # Обязательно вызываем валидацию перед сохранением
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class TinkoffSandboxAccount(models.Model):
    """Аккаунты песочницы."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sandbox_accounts",
    )
    description = models.CharField(
        max_length=255, blank=True, help_text="Краткое описание стратегии"
    )
    account_id = models.CharField(
        max_length=50, unique=True
    )  # models.UUIDField()
    access_token = EncryptedCharField(max_length=255)

    def __str__(self):
        return f"Sandbox: {self.account_id}"


class SandboxMoney(models.Model):
    """Валютные позиции (деньги) на аккаунте."""

    # Связка по полю account_id
    account = models.ForeignKey(
        TinkoffSandboxAccount,
        to_field="account_id",
        on_delete=models.CASCADE,
        related_name="money",
    )
    currency = models.CharField(max_length=10, verbose_name="валюта")
    balance = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    blocked = models.DecimalField(max_digits=20, decimal_places=9, default=0)

    @property
    def free_money(self):
        return self.balance - self.blocked

    def __str__(self):
        return (
            f"{self.account_id} - {self.currency.upper()}: {self.free_money}"
        )

    class Meta:
        verbose_name_plural = "Sandbox Money"
        unique_together = ("account", "currency")
        indexes = [
            models.Index(fields=["account", "currency"]),
        ]
