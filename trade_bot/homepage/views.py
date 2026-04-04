from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse

from django.views import View

from homepage.functions import get_moex_index_value_direct

from homepage.tasks import add_numbers, get_data_moex_index

from celery.result import AsyncResult
from trade_bot.celery import app

class HomeView(View):
    """Главная страница"""
    def get(self, request):

        task_moex = get_data_moex_index.delay("IMOEX")
        task_moexbc = get_data_moex_index.delay("MOEXBC")
        task_rugolg = get_data_moex_index.delay("RUGOLD")
        task_rvi = get_data_moex_index.delay("RVI")
        task_moexog = get_data_moex_index.delay("MOEXOG")

    

        task_group = (task_moex.id, task_moexbc.id, task_rugolg.id, task_rvi.id, task_moexog.id)
       

        messages.info(self.request, f'Домашняя страница!')
        context = {
          "task_group":task_group,
        }
        return render(request, 'home.html', context)


def get_task_status(request, task_id):
    """Возвращает текущий статус задачи."""
    if not task_id:
        return JsonResponse({'status': 'ERROR', 'message': 'No task_id'})

    task = AsyncResult(task_id)

    if task.state == 'PROGRESS':
        # Возвращаем данные о прогрессе, которые мы отправили через update_state
        return JsonResponse({
            'status': 'PROGRESS',
        })
    elif task.state == 'SUCCESS':
        # Задача выполнена, возвращаем результат
        return JsonResponse({
            'status': 'SUCCESS',
            'data': task.result.get('data', [])
        })
    elif task.state == 'FAILURE':
        return JsonResponse({
            'status': 'FAILURE',
            'error': str(task.info)
        })
    else:
        # PENDING, STARTED, etc.
        return JsonResponse({'status': task.state})

