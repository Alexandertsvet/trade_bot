from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
)
from t_tech.invest import Client, RequestError
from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX
from t_tech.invest.schemas import MoneyValue

from t_invest.models import SandboxPostOrderRequest

from .models import TinkoffSandboxAccount, User


class UserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "имя пользователя...",
                }
            ),
            "email": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "email...",
                    "type": "email",
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите пароль...",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "повторите ввод пароля...",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and User.objects.exists():
            # Принудительно вешаем ошибку на поле username
            self.add_error(
                "username",
                "Регистрация невозможна: в системе уже есть пользователь.",
            )
        return cleaned_data


class UserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Комментарий...",
                }
            ),
            "email": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "email..."}
            ),
        }


class LoginView_form(AuthenticationForm):
    class Meta(AuthenticationForm):
        model = User
        fields = ("username", "password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите login пользователя...",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите пароль...",
            }
        )


class PasswordChangeForm_form(PasswordChangeForm):
    class Meta(PasswordChangeForm):
        model = User
        field_order = ["old_password", "new_password1", "new_password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите старый пароль...",
            }
        )
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите новый пароль...",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "повторите ввод нового пароля...",
            }
        )


class PasswordResetForm_form(PasswordResetForm):
    class Meta(PasswordResetForm):
        model = User
        field_order = ["email"]
        widgets = {
            "email": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "email...",
                    "type": "email",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите адрес электронной почты...",
            }
        )


class SetPasswordForm_form(SetPasswordForm):
    class Meta(PasswordResetForm):
        model = User
        field_order = ["new_password1", "new_password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "введите новый пароль...",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "повторите ввод нового пароля...",
            }
        )


from django import forms


class SandboxAccountForm(forms.ModelForm):
    class Meta:
        model = TinkoffSandboxAccount
        fields = ["access_token", "description"]
        widgets = {
            "access_token": forms.PasswordInput(
                render_value=True,
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "t.XyZ...",
                },
            ),
            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
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
                with Client(token, target=INVEST_GRPC_API_SANDBOX) as client:
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


class SandboxOrderForm(forms.ModelForm):
    class Meta:
        model = SandboxPostOrderRequest
        # Указываем, какие поля выводить в форме (исключаем автоматический order_id)
        fields = [
            "account_id",
            "instrument_id",
            "quantity",
            "price",
            "direction",
            "order_type",
            "time_in_force",
            "price_type",
            "confirm_margin_trade",
        ]

        widgets = {
            "account_id": forms.Select(attrs={"class": "form-select"}),
            "instrument": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Введите количество лотов",
                    "min": "1",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0.000000000",
                    "step": "0.000000001",
                }
            ),
            # Для Enum (IntegerChoices) используем форму выбора form-select
            "direction": forms.Select(attrs={"class": "form-select"}),
            "order_type": forms.Select(attrs={"class": "form-select"}),
            "time_in_force": forms.Select(attrs={"class": "form-select"}),
            "price_type": forms.Select(attrs={"class": "form-select"}),
            # Чекбокс требует отдельного класса в Bootstrap
            "confirm_margin_trade": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                    "role": "switch",  # Превратит чекбокс в красивый тумблер-переключатель
                }
            ),
        }

    def clean(self):
        """Дополнительная валидация на уровне всей формы"""
        cleaned_data = super().clean()
        order_type = cleaned_data.get("order_type")
        price = cleaned_data.get("price")

        # Бизнес-логика: если заявка лимитная, цена обязательна
        if (
            order_type == SandboxPostOrderRequest.OrderType.ORDER_TYPE_LIMIT
            and not price
        ):
            self.add_error(
                "price", "Для лимитной заявки необходимо указать цену."
            )
        return cleaned_data
