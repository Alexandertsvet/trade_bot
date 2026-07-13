import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "data"

    def ready(self):
        logger.info(f"СИСТЕМА УСПЕШНО ИНИЦИАЛИЗИРОВАНА, {self.name}")
