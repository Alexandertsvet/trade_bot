from django.shortcuts import render
from django.contrib import messages

from django.views import View

class HomeView(View):
    """Главная страница"""
    def get(self, request):

        messages.info(self.request, f'Домашняя страница!')
        context = {
          
        }
        return render(request, 'home.html', context)
