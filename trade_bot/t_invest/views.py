import json
import logging
import calendar

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, DetailView, ListView, View
from django.views.generic.edit import CreateView
from t_tech.invest import (
    Client,
    RequestError,
)

from data.models import FinancialInstrument
from t_invest.forms import AccauntForm
from t_invest.functions import save_tinkoff_portfolio
from t_invest.models import FavoriteInstrument, TinkoffAccaunt
from trade_bot.settings import client_clickhouse
from data.models import TradeSignal

import pandas as pd

logger = logging.getLogger(__name__)


class AccauntCreateView(LoginRequiredMixin, CreateView):
    form_class = AccauntForm
    template_name = "t_invest/accaunt/account_create.html"
    success_url = reverse_lazy("t_invest:accaunt_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.error(self.request, "Успешно создан счет.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Ошибка при заполнении формы. Проверьте данные. API KEY",
        )
        return super().form_invalid(form)


class AccauntDeleteView(LoginRequiredMixin, DeleteView):
    model = TinkoffAccaunt
    template_name = "t_invest/accaunt/accaunt_delete.html"
    success_url = reverse_lazy("t_invest:accaunt_list")

    def get_queryset(self):
        return TinkoffAccaunt.objects.filter(user=self.request.user)

    def form_valid(self, form):
        account = self.get_object()
        try:
            with Client(account.access_token) as client:
                client.sandbox.close_sandbox_account(
                    account_id=account.account_id
                )
                messages.success(
                    self.request,
                    f"Аккаунт {account.account_id} удален из системы Тинькофф.",
                )
        except RequestError as e:
            messages.warning(
                self.request,
                f"Запись удалена только локально. API Тинькофф вернул ошибку: {e.metadata.message}",
            )
        except Exception as e:
            messages.error(
                self.request, f"Ошибка при обращении к API: {str(e)}"
            )
        return super().form_valid(form)


class AccauntListView(LoginRequiredMixin, ListView):
    model = TinkoffAccaunt
    template_name = "t_invest/accaunt/t_invest_accaunt_list.html"
    context_object_name = "accaunts"

    def get_queryset(self):
        return (
            TinkoffAccaunt.objects.filter(user=self.request.user)
            .select_related("portfolio")
            .prefetch_related(
                "portfolio__positions", "portfolio__positions__instrument"
            )
        )


class UpdatePortfolio(LoginRequiredMixin, View):
    def post(self, request, pk):
        accaunt = get_object_or_404(TinkoffAccaunt, pk=pk, user=request.user)
        token = accaunt.access_token
        account_id = accaunt.account_id
        try:
            with Client(token, target=settings.TARGET_TRADE) as client:
                portfolio_response = client.operations.get_portfolio(
                    account_id=account_id
                )
                save_tinkoff_portfolio(
                    account_id=account_id,
                    token=token,
                    portfolio_data=portfolio_response,
                )
                logger.info(f"портфолио для аккаунта {account_id} обновлено.")
                messages.success(request, "Выполнено обновление портфолио.")
        except RequestError as e:
            logger.error(f"Ошибка Tinkoff API для аккаунта {account_id}: {e}")
        except Exception as e:
            logger.error(
                f"Непредвиденная ошибка при создании портфеля {account_id}: {e}"
            )
        return redirect("t_invest:accaunt_list")


class TradingOperation(LoginRequiredMixin, DetailView):
    model = TinkoffAccaunt
    template_name = "t_invest/traiding/traiding_operation.html"
    context_object_name = "accaunt"

    def get_queryset(self):
        return TinkoffAccaunt.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["instruments"] = (
            FinancialInstrument.objects.all()
            .filter(class_code="TQBR")
            .order_by("ticker")
        )
        favorite_ids = FavoriteInstrument.objects.filter(
            user__user=self.request.user
        ).values_list("instrument__uid", flat=True)
        context["favorite_ids"] = {str(uid) for uid in favorite_ids}
        return context


class FavoriteInstrumentListView(LoginRequiredMixin, ListView):
    """Отображение списка избранных инструментов текущего пользователя."""

    model = FavoriteInstrument
    template_name = "t_invest/accaunt/favorite_instruments.html"
    context_object_name = "favorite_instruments"

    def get_queryset(self):
        return FavoriteInstrument.objects.filter(
            user__user=self.request.user
        ).select_related("instrument")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        favorite_ids = FavoriteInstrument.objects.filter(
            user__user=self.request.user
        ).values_list("instrument__uid", flat=True)
        context["favorite_ids"] = {str(uid) for uid in favorite_ids}
        return context


class ToggleFavoriteView(LoginRequiredMixin, View):
    """Универсальная точка переключения избранного для любого шаблона."""

    def post(self, request, uid):
        instrument = get_object_or_404(FinancialInstrument, uid=uid)
        account = get_object_or_404(TinkoffAccaunt, user=request.user)
        favorite = FavoriteInstrument.objects.filter(
            user=account, instrument=instrument
        )
        if favorite.exists():
            favorite.delete()
            action = "removed"
        else:
            FavoriteInstrument.objects.create(
                user=account, instrument=instrument
            )
            action = "added"
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "success", "action": action})
        return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def delete_favorite_view(request, ticker):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        account = get_object_or_404(TinkoffAccaunt, user=request.user)
        try:
            favorite_item = get_object_or_404(
                FavoriteInstrument, user=account, instrument__ticker=ticker
            )
            favorite_item.delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": str(e)}, status=400
            )
    return JsonResponse(
        {"success": False, "error": "Invalid request"}, status=400
    )


class TraidingTerminal(LoginRequiredMixin, View):
    template_name = "t_invest/traiding/traiding_terminal.html"
    context_object_name = "accaunt"

    def get_queryset(self):
        return TinkoffAccaunt.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        """Этот метод перехватывает GET-запрос и рендерит страницу"""
        # 1. Получаем аккаунты
        accaunt = self.get_queryset()
        
        # 2. Получаем свечи из ClickHouse
        df = client_clickhouse.get_latest_window(secid="GAZP", window_size=200)
        df["tradetime"] = pd.to_datetime(df["tradetime"], errors="coerce")
        df["time"] = df["tradetime"].dt.tz_localize(None)
        df["time"] = df["time"].astype("datetime64[s]").astype("int64")
        
        rename_dict = {
            "pr_open": "open",
            "pr_high": "high",
            "pr_low": "low",
            "pr_close": "close",
        }
        df_charts = df[["time", "pr_open", "pr_high", "pr_low", "pr_close"]].rename(columns=rename_dict)
        raw_data = df_charts.reset_index(drop=True).to_dict(orient="records")
        data = json.dumps(raw_data, indent=4)

        # 3. Получаем торговые сигналы и форматируем их для lightweight-charts markers
        # Извлекаем минимальное и максимальное время свечей, чтобы отфильтровать только нужные сигналы
        if not df.empty:
            min_time = df["tradetime"].min()
            max_time = df["tradetime"].max()
            trade_signals = TradeSignal.objects.filter(tradetime__range=(min_time, max_time))
        else:
            trade_signals = TradeSignal.objects.all()


        markers_list = []
        for signal in trade_signals:
            dt_local = timezone.localtime(signal.tradetime)

            # 2. Отрезаем временную зону, делая объект naive (как это делает Pandas)
            dt_naive = dt_local.replace(tzinfo=None)
            # 3. ИСПРАВЛЕНИЕ: Используем calendar.timegm вместо .timestamp()
            # Данный метод преобразует naive-время строго по эпохе UTC-0 (точно так же, как astype("int64") в Pandas)
            signal_timestamp = calendar.timegm(dt_naive.timetuple())

            # Определяем параметры отображения маркера в зависимости от типа сигнала
            if signal.signal == 'BUY':
                color = '#26a69a'      # Зеленый
                position = 'belowBar'  # Под свечой
                shape = 'arrowUp'      # Стрелка вверх
                marker_text = (f"{signal.signal}({signal.confidence:.3f})|S:{signal.prob_sell:.3f}"
            )

            elif signal.signal == 'SELL':
                color = '#ef5350'      # Красный
                position = 'aboveBar'  # Над свечой
                shape = 'arrowDown'    # Стрелка вниз
                marker_text = (f"{signal.signal}({signal.confidence:.3f})|B:{signal.prob_buy:.3f}"
            )
            elif signal.signal == 'HOLD':
                color = '#90a4ae'      # Серый для HOLD
                position = 'inBar'
                shape = 'circle'
                marker_text = (
                f"{signal.signal} ({signal.confidence:.3f}) | "
                f"B:{signal.prob_buy:.3f} S:{signal.prob_sell:.3f}"
                )

            markers_list.append({
                'time': signal_timestamp,
                'position': position,
                'color': color,
                'shape': shape,
                'text': marker_text,
            })
        
        markers_list = sorted(markers_list, key=lambda x: x['time'])
        markers_data = json.dumps(markers_list, indent=4)

        # 4. Формируем контекст
        context = {
            "accaunt": accaunt,
            "active_accaunt": accaunt.first(),
            "data": data,            
            "markers": markers_data, 
        }

        return render(request, self.template_name, context)
