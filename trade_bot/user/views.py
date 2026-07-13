import json
import uuid

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    View,
)
from django.views.generic.edit import CreateView
from t_tech.invest import (
    Client,
    OrderDirection,
    OrderType,
    RequestError,
)
from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX
from t_tech.invest.schemas import MoneyValue

from data.models import FinancialInstrument
from user.forms import SandboxOrderForm
from user.models import TinkoffSandboxAccount
from user.tasks import save_data_post_order

from .forms import (
    LoginView_form,
    PasswordChangeForm_form,
    PasswordResetForm_form,
    SetPasswordForm_form,
    UserCreationForm,
)


class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("user:login")
    template_name = "registration/signup.html"


class LoginView(auth_views.LoginView):
    form_class = LoginView_form
    success_url = reverse_lazy("homepage:homepage")
    template_name = "registration/login.html"


class LogoutView(auth_views.LogoutView):
    success_url = reverse_lazy("homepage:homepage")


class PasswordChangeView(auth_views.PasswordChangeView):
    form_class = PasswordChangeForm_form
    success_url = reverse_lazy("user:login")
    template_name = "registration/password_change_form.html"


class PasswordResetView(auth_views.PasswordResetView):
    form_class = PasswordResetForm_form
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    template_name = "registration/password_reset_form.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = SetPasswordForm_form
    success_url = reverse_lazy("password_reset_complete")
    template_name = "registration/password_reset_confirm.html"


from user.forms import SandboxAccountForm


class SandboxAccountCreateView(LoginRequiredMixin, CreateView):
    form_class = SandboxAccountForm
    template_name = "sandbox/sandbox_account_form.html"
    success_url = reverse_lazy("user:sandbox_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.error(
            self.request, "Успешно создан счет, пополнен на 100 000 руб."
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Ошибка при заполнении формы. Проверьте данные. API KEY",
        )
        return super().form_invalid(form)


class SandboxAccountListView(LoginRequiredMixin, ListView):
    model = TinkoffSandboxAccount
    template_name = "sandbox/sandbox_account_list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return TinkoffSandboxAccount.objects.filter(
            user=self.request.user
        ).prefetch_related("money")


class SandboxAccountDeleteView(LoginRequiredMixin, DeleteView):
    model = TinkoffSandboxAccount
    template_name = "sandbox/sanbox_account_delete.html"
    success_url = reverse_lazy("user:sandbox_list")

    def get_queryset(self):
        return TinkoffSandboxAccount.objects.filter(user=self.request.user)

    def form_valid(self, form):
        # Получаем объект до его удаления из БД
        account = self.get_object()

        try:
            with Client(account.access_token) as client:
                # Закрываем конкретный аккаунт в песочнице Тинькофф
                client.sandbox.close_sandbox_account(
                    account_id=account.account_id
                )
                messages.success(
                    self.request,
                    f"Аккаунт {account.account_id} удален из системы Тинькофф.",
                )
        except RequestError as e:
            # Если в Тинькофф аккаунт уже удален или токен неверный,
            # мы все равно удалим его из нашей БД, но предупредим пользователя
            messages.warning(
                self.request,
                f"Запись удалена только локально. API Тинькофф вернул ошибку: {e.metadata.message}",
            )
        except Exception as e:
            messages.error(
                self.request, f"Ошибка при обращении к API: {str(e)}"
            )

        return super().form_valid(form)


class SandboxAccountAdd(LoginRequiredMixin, CreateView):
    model = TinkoffSandboxAccount
    fields = []  # Список полей пуст, так как мы ничего не вводим вручную
    template_name = "sandbox/sanbox_account_add.html"
    success_url = reverse_lazy("user:sandbox_list")

    def form_valid(self, form):
        last_account = TinkoffSandboxAccount.objects.filter(
            user=self.request.user
        ).last()

        if not last_account:
            messages.error(
                self.request,
                "У вас нет сохраненных токенов. Сначала добавьте токен вручную.",
            )
            return redirect("user:sandbox_add")

        token = last_account.access_token

        # 2. Подготавливаем новую запись
        form.instance.user = self.request.user
        form.instance.access_token = token  # Копируем токен из старой записи

        try:
            with Client(token) as client:
                # 3. Открываем счет в API
                api_account = client.sandbox.open_sandbox_account()
                form.instance.account_id = api_account.account_id
                # 4. Пополняем счет
                pay_in_amount = MoneyValue(
                    units=100000, nano=0, currency="rub"
                )
                client.sandbox.sandbox_pay_in(
                    account_id=api_account.account_id, amount=pay_in_amount
                )

                messages.success(
                    self.request,
                    f"Новый счет {api_account.account_id} успешно открыт.",
                )
                messages.success(
                    self.request,
                    f"Новый счет {api_account.account_id} успешно пополнен на 100 000 руб.",
                )

        except Exception as e:
            messages.error(self.request, f"Ошибка при работе с API: {str(e)}")
            return self.form_invalid(form)

        return super().form_valid(form)


class SandboxAccountDelAll(LoginRequiredMixin, TemplateView):
    template_name = "sandbox/sanbox_account_del_all.html"
    context_object_name = "accounts"

    def get_queryset(self):
        return TinkoffSandboxAccount.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Вручную передаем данные в контекст шаблона
        context["total_accounts"] = TinkoffSandboxAccount.objects.all().count()
        return context

    def post(self, request, *args, **kwargs):
        user_accounts = TinkoffSandboxAccount.objects.filter(
            user=self.request.user
        )

        if not user_accounts.exists():
            messages.warning(self.request, "Счет не найден.")
            return redirect("user:sandbox_list")

        token = user_accounts.last().access_token

        try:
            with Client(token, target=INVEST_GRPC_API_SANDBOX) as client:
                response = client.users.get_accounts()
                for account in response.accounts:
                    client.sandbox.close_sandbox_account(account_id=account.id)
                user_accounts.delete()
                messages.success(
                    self.request, "Все счета песочницы успешно закрыты."
                )
        except RequestError as e:
            messages.error(
                self.request,
                f"Ошибка API: {e.metadata.message if e.metadata else str(e)}",
            )
        except Exception as e:
            messages.error(self.request, f"Ошибка: {str(e)}")

        return redirect("user:sandbox_list")


class TinkoffSandboxAccountDetailView(LoginRequiredMixin, DetailView):
    model = TinkoffSandboxAccount
    template_name = "sandbox/sandbox_detail/sandbox_detail.html"
    context_object_name = "sandbox_account"

    def get_queryset(self):
        # 1. Фильтруем аккаунты, чтобы юзер не мог подсмотреть чужой account_id через URL
        # 2. Жадная загрузка (prefetch_related) денег и позиций (включая связанные инструменты) одним махом
        return (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .prefetch_related("money")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_instruments"] = (
            FinancialInstrument.objects.all()
            .filter(class_code="TQBR")
            .order_by("ticker")
        )

        return context


class AddPositionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Гарантируем, что аккаунт принадлежит текущему пользователю
        account = get_object_or_404(
            TinkoffSandboxAccount, pk=pk, user=request.user
        )

        # Получаем данные из HTML-формы (атрибуты name="...")
        instrument_id = request.POST.get("instrument_id")  # instrument.uid

        quantity = int(request.POST.get("quantity", 1))

        instrument = get_object_or_404(FinancialInstrument, uid=instrument_id)
        try:
            with Client(
                account.access_token, target=INVEST_GRPC_API_SANDBOX
            ) as client:
                print(client)
                unique_order_id = str(uuid.uuid4())
                order = client.orders.post_order(
                    instrument_id=instrument_id,
                    quantity=quantity,
                    direction=OrderDirection.ORDER_DIRECTION_BUY,
                    account_id=account.account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    order_id=unique_order_id,
                )
                messages.info(
                    self.request,
                    f"Ордер execution_report_status: {order.execution_report_status}",
                )
                order_post = save_data_post_order.delay(unique_order_id)
                print(order)

            return redirect("user:sandbox_detail", pk=account.pk)
        except RequestError as e:
            messages.error(
                self.request,
                f"Ошибка API T-Invest: {e.details if e.details else 'Неверные параметры или токен'}",
            )
            messages.error(
                self.request,
                f"Ошибка API: {e.metadata.message if e.metadata else str(e)}",
            )
            return redirect("user:sandbox_detail", pk=account.pk)
        except Exception as e:
            messages.error(
                self.request, f"Критическая ошибка подключения: {e}"
            )
            return redirect("user:sandbox_detail", pk=account.pk)


class AddPositionPostOrderRequest(LoginRequiredMixin, View):
    def post(self, request, pk):
        """Обработка данных формы и отправка в API / БД при POST-запросе"""
        account = get_object_or_404(
            TinkoffSandboxAccount, pk=pk, user=request.user
        )
        form = SandboxOrderForm(request.POST)
        if form.is_valid():
            order_instance = form.save(commit=False)
            if not order_instance.order_id:
                order_instance.order_id = uuid.uuid4()

            print(order_instance)

            try:
                with Client(
                    account.access_token, target=INVEST_GRPC_API_SANDBOX
                ) as client:
                    sdk_arguments = order_instance.to_sdk_args()
                    print(sdk_arguments)
                    sdk_response = client.orders.post_order(**sdk_arguments)

                    print(sdk_response.execution_report_status)

                    messages.info(
                        self.request,
                        f"Ордер execution_report_status: {sdk_response.execution_report_status}",
                    )
                    print(order_instance)
                    print("-------------------------")
                    order_instance.save()
                    form.save_m2m()
                    messages.info(self.request, "Ордер записан в базу.")

                    print("-------------------------")
                    print(type(sdk_response))
                    json_output = json.dumps(
                        sdk_response.__dict__,
                        indent=2,
                        ensure_ascii=False,
                        default=str,  # обрабатывает несериализуемые типы (даты, Decimal и т. д.)
                    )
                    print(json_output)

                    order_post = save_data_post_order.delay(json_output)
                    print("-------------------------")

                return redirect("user:sandbox_detail", pk=account.pk)
            except RequestError as e:
                messages.error(
                    self.request,
                    f"Ошибка API T-Invest: {e.details if e.details else 'Неверные параметры или токен'}",
                )
                messages.error(
                    self.request,
                    f"Ошибка API: {e.metadata.message if e.metadata else str(e)}",
                )
                return render(
                    request,
                    "sandbox/sandbox_detail/sandbox_order_form.html",
                    {"form": form},
                )
            except Exception as e:
                messages.error(
                    self.request, f"Критическая ошибка подключения: {e}"
                )
                print(e)
                return render(
                    request,
                    "sandbox/sandbox_detail/sandbox_order_form.html",
                    {"form": form},
                )
        return render(
            request,
            "sandbox/sandbox_detail/sandbox_order_form.html",
            {"form": form},
        )
