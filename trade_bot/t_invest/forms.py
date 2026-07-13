from django import forms
from django.conf import settings
from t_tech.invest import Client, RequestError
from t_tech.invest.schemas import MoneyValue

from t_invest.models import TinkoffAccaunt


class AccauntForm(forms.ModelForm):
    class Meta:
        model = TinkoffAccaunt
        fields = ["access_token", "access_token_algopack", "description"]
        widgets = {
            "access_token": forms.PasswordInput(
                render_value=True,
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "t.XyZ...",
                },
            ),
            "access_token_algopack": forms.PasswordInput(
                render_value=True,
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Bearer eyJhb...",
                },
            ),
            "description": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Краткое описание стратегии",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        token = cleaned_data.get("access_token")

        if token:
            try:
                # 1. Проверяем токен и получаем account_id прямо здесь
                with Client(token, target=settings.TARGET_TRADE) as client:
                    response = client.sandbox.open_sandbox_account()
                    account_id = response.account_id

                    # Пополняем счет сразу для проверки работоспособности
                    client.sandbox.sandbox_pay_in(
                        account_id=account_id,
                        amount=MoneyValue(
                            units=100000, nano=0, currency="rub"
                        ),
                    )
                    # Сохраняем полученный ID в cleaned_data, чтобы достать его в save()
                    cleaned_data["account_id"] = account_id

            except RequestError as e:
                error_msg = (
                    e.metadata.message if e.metadata else "Неверный токен"
                )
                raise forms.ValidationError(f"Ошибка API: {error_msg}")
            except Exception as e:
                raise forms.ValidationError(
                    f"Не удалось подключиться: {str(e)}"
                )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Достаем account_id, который мы сохранили в методе clean()
        instance.account_id = self.cleaned_data.get("account_id")
        if commit:
            instance.save()
            self.save_m2m()
        return instance
