import json

from celery.result import AsyncResult
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from homepage.tasks import get_data_moex_index
from trade_bot.settings import client_clickhouse

import pandas as pd


class HomeView(View):
    """Главная страница"""

    def get(self, request, *args, **kwargs):

        task_moex = get_data_moex_index.delay("IMOEX")
        task_moexbc = get_data_moex_index.delay("MOEXBC")
        task_rugolg = get_data_moex_index.delay("RUGOLD")
        task_rvi = get_data_moex_index.delay("RVI")
        task_moexog = get_data_moex_index.delay("MOEXOG")
        task_group = (
            task_moex.id,
            task_moexbc.id,
            task_rugolg.id,
            task_rvi.id,
            task_moexog.id,
        )
        messages.info(self.request, "Домашняя страница!")
        # -----------------------------------
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
        df_charts = df[
            ["time", "pr_open", "pr_high", "pr_low", "pr_close"]
        ].rename(columns=rename_dict)
        raw_data = df_charts.reset_index(drop=True).to_dict(orient="records")
        data = json.dumps(raw_data, indent=4)
        # ----------------------------------------
        context = {"task_group": task_group, "chart_data": data}
        return render(request, "home.html", context)


def get_task_status(request, task_id):
    """Возвращает текущий статус задачи."""
    if not task_id:
        return JsonResponse({"status": "ERROR", "message": "No task_id"})

    task = AsyncResult(task_id)

    if task.state == "PROGRESS":
        # Возвращаем данные о прогрессе, которые мы отправили через update_state
        return JsonResponse(
            {
                "status": "PROGRESS",
            }
        )
    elif task.state == "SUCCESS":
        # Задача выполнена, возвращаем результат
        return JsonResponse(
            {"status": "SUCCESS", "data": task.result.get("data", [])}
        )
    elif task.state == "FAILURE":
        return JsonResponse({"status": "FAILURE", "error": str(task.info)})
    else:
        # PENDING, STARTED, etc.
        return JsonResponse({"status": task.state})
