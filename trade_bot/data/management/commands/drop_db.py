from django.core.management.base import BaseCommand
from data.models import TradeData

class Command(BaseCommand):
    help = 'Удаление базы данных'

    def handle(self, *args, **kwargs):
        TradeData.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(f'Данные успешно удалены! '))