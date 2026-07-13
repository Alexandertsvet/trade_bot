import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from t_tech.invest import Client, RequestError

from t_invest.functions import save_tinkoff_portfolio
from t_invest.models import TinkoffAccaunt

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TinkoffAccaunt)
def auto_create_portfolio_on_account_save(sender, instance, created, **kwargs):
    """
    Сигнал: срабатывает автоматически после сохранения модели TinkoffAccount.
    """
    # Выполняем первичную загрузку только при создании нового аккаунта
    if created:
        token = instance.access_token
        account_id = instance.account_id

        try:
            # Делаем запрос к API Тинькофф
            with Client(token, target=settings.TARGET_TRADE) as client:
                portfolio_response = client.operations.get_portfolio(
                    account_id=account_id
                )

                # Сохраняем данные в БД через наш сервис
                save_tinkoff_portfolio(
                    account_id=account_id,
                    token=token,
                    portfolio_data=portfolio_response,
                )
                logger.info(
                    f"Портфель для аккаунта {account_id} успешно инициализирован."
                )

        except RequestError as e:
            # Логируем ошибку, если токен невалидный или API недоступно
            logger.error(f"Ошибка Tinkoff API для аккаунта {account_id}: {e}")
        except Exception as e:
            # Перестраховка на случай других системных сбоев
            logger.error(
                f"Непредвиденная ошибка при создании портфеля {account_id}: {e}"
            )
