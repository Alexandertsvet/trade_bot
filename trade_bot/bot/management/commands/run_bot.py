import logging
import sys
import time
import uuid
from datetime import datetime

from django.core.management.base import BaseCommand
from django.shortcuts import get_object_or_404
from t_tech.invest import (
    Client,
    OrderDirection,
    OrderType,
    RequestError,
)
from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX

from bot.functions import get_quantity_all, receive_and_save, update_data, cast_to_decimal
from bot.ml_models import (
    RealTimeMetaEnsemble,
)
from bot.models import BotConfiguration
from data.models import FinancialInstrument
from t_invest.models import (
    TinkoffAccaunt,
    SandboxPostOrderResponse,
    SandboxPostOrderRequest,
)
from trade_bot.settings import ALGOPACK_KEY, BASE_DIR, client_clickhouse
from user.models import User

logger = logging.getLogger(__name__)

headers = {
    "Accept": "application/json",
    "Authorization": ALGOPACK_KEY,
}
proper_model_dir = BASE_DIR / "bot/ml_models/prophet_model.json"
catboost_model_5 = BASE_DIR / "bot/ml_models/catboost_model_5.cbm"
catboost_model_10 = BASE_DIR / "bot/ml_models/catboost_model_10.cbm"
catboost_model_15 = BASE_DIR / "bot/ml_models/catboost_model_15.cbm"
meta_classifier_path = BASE_DIR / "bot/ml_models/unified_meta_classifier.cbm"

cb_paths = {
    "5": catboost_model_5,
    "10": catboost_model_10,
    "15": catboost_model_15,
}


class Command(BaseCommand):
    help = "Запуск торгового бота"

    def add_arguments(self, parser):
        parser.add_argument("pk", type=int, help="ID аккаунта (Primary Key)")
        parser.add_argument(
            "user_id", type=int, help="ID владельца аккаунта (User ID)"
        )

    def handle(self, *args, **options):
        pk = options["pk"]
        user_id = options["user_id"]
        self.stdout.write(
            self.style.SUCCESS(f"Бот успешно запущен...{datetime.now()}")
        )
        logger.info(f"Бот успешно запущен...{datetime.now()}")
        try:
            count_gazp = client_clickhouse.execute(
                "SELECT count() FROM test_trade.test_tradestats WHERE secid = 'GAZP'"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Обновляет данные GAZP, кол-во до обновления {count_gazp}"
                )
            )
            update_data(client_clickhouse, headers)
            count_gazp_update = client_clickhouse.execute(
                "SELECT count() FROM test_trade.test_tradestats WHERE secid = 'GAZP'"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Кол-во после обновления {count_gazp_update}"
                )
            )
            self.stdout.write(self.style.SUCCESS("Данные обновлены..."))
            self.stdout.write(self.style.SUCCESS("Удаление дубликатов"))
            client_clickhouse.drop_duplicated("test_trade", "test_tradestats")
            count_gazp_drop = client_clickhouse.execute(
                "SELECT count() FROM test_trade.test_tradestats WHERE secid = 'GAZP'"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Дубликаты удалены...кол-во {count_gazp_drop}"
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.SUCCESS(f"Ошибка обновления базы данных {e}")
            )

        try:
            instrument = FinancialInstrument.objects.get(ticker="GAZP")
        except FinancialInstrument.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("Инструмент GAZP не найден в базе данных.")
            )
            sys.exit(1)

        config, created = BotConfiguration.objects.get_or_create(
            instrument=instrument
        )
        if config.is_available_trade:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Торговый инструмент доступен для торговли...{instrument}"
                )
            )
            config.is_active = True
            config.save(update_fields=["is_active"])
            self.stdout.write(
                self.style.SUCCESS("Статус бота в БД изменен на: Активен")
            )
        else:
            self.stdout.write(
                f"Торговый инструмент не доступен для торговли...{instrument}"
            )
            config.is_active = False
            config.save(update_fields=["is_active"])
            sys.exit(1)

        try:
            meta_model = RealTimeMetaEnsemble(
                proper_model_dir, cb_paths, meta_classifier_path
            )
            user = User.objects.get(pk=user_id)
            account = get_object_or_404(TinkoffAccaunt, pk=pk, user=user)
            quantity = 10
            quantity_sum = get_quantity_all(account, INVEST_GRPC_API_SANDBOX)
            while True:
                try:
                    config.refresh_from_db()
                    if not config.is_active:
                        self.stdout.write(
                            "Бот остановлен (is_active=False). Ожидание запуска..."
                        )
                        time.sleep(5)
                        continue

                    # --- ПОЛУЧЕНИЕ ДАННЫХ ---
                    if receive_and_save(headers):
                        # --- ЗДЕСЬ НАЧИНАЕТСЯ ЛОГИКА ТОРГОВЛИ ---
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Получение агрегируемых данных {config.instrument}..."
                            )
                        )
                        df = client_clickhouse.get_latest_window(
                            secid="GAZP", window_size=200
                        )
                        result = meta_model.predict_trade_signal(df)

                        print(result)
                        signal = result["signal"]
                        logger.info(f"Результат предсказания модели: {signal}")

                        match signal:
                            case "BUY":
                                try:
                                    with Client(
                                        account.access_token,
                                        target=INVEST_GRPC_API_SANDBOX,
                                    ) as client:
                                        unique_order_id = str(uuid.uuid4())
                                        order = client.orders.post_order(
                                            instrument_id=str(instrument.uid),
                                            quantity=quantity,
                                            direction=OrderDirection.ORDER_DIRECTION_BUY,
                                            account_id=account.account_id,
                                            order_type=OrderType.ORDER_TYPE_MARKET,
                                            order_id=unique_order_id,
                                        )
                                        logger.info(
                                            f"Ордер execution_report_status: {order.execution_report_status}"
                                        )
                                        if order.execution_report_status==1:
                                                order_request = SandboxPostOrderRequest.objects.create(
                                                    account_id=account,
                                                    instrument_id=instrument,
                                                    quantity=quantity,
                                                    direction=OrderDirection.ORDER_DIRECTION_BUY,
                                                    order_type=OrderType.ORDER_TYPE_MARKET,
                                                    order_id=unique_order_id
                                                )
                                                logger.info(f"Ордер запрос: {order_request}")

                                                order_response = SandboxPostOrderResponse.objects.create(
                                                    order_response=order_request,
                                                    order_id=order.order_id,
                                                    order_request_id=order.order_request_id,
                                                    instrument_uid=order.instrument_uid,
                                                    figi=order.figi,
                                                    execution_report_status=order.execution_report_status,
                                                    direction=order.direction,
                                                    order_type=order.order_type,
                                                    lots_requested=order.lots_requested,
                                                    lots_executed=order.lots_executed,
                                                    initial_order_price=cast_to_decimal(order.initial_order_price),
                                                    executed_order_price=cast_to_decimal(order.executed_order_price),
                                                    total_order_amount=cast_to_decimal(order.total_order_amount),
                                                    initial_commission=cast_to_decimal(order.initial_commission),
                                                    executed_commission=cast_to_decimal(order.executed_commission),
                                                    aci_value=cast_to_decimal(order.aci_value),
                                                    initial_security_price=cast_to_decimal(order.initial_security_price),
                                                    initial_order_price_pt=cast_to_decimal(order.initial_order_price_pt),
                                                    message=order.message,
                                                    response_metadata=order.response_metadata,
                                                )
                                                logger.info(f"Ордер ответ сохранен: {order}")
                                        logger.info(f"Ордер ответ: {order}")
                                        quantity_sum += quantity
                                except RequestError as e:
                                    logger.error(
                                        f"Ошибка API T-Invest: {e.details if e.details else 'Неверные параметры или токен'}"
                                    )
                                    logger.error(
                                        f"Ошибка API: {e.metadata.message if e.metadata else str(e)}"
                                    )
                                    return redirect(
                                        "user:sandbox_detail", pk=account.pk
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Критическая ошибка подключения: {e}"
                                    )
                            case "SELL":
                                if quantity_sum >= 10:
                                    try:
                                        with Client(
                                            account.access_token,
                                            target=INVEST_GRPC_API_SANDBOX,
                                        ) as client:
                                            unique_order_id = str(uuid.uuid4())
                                            order = client.orders.post_order(
                                                instrument_id=str(
                                                    instrument.uid
                                                ),
                                                quantity=quantity_sum,
                                                direction=OrderDirection.ORDER_DIRECTION_SELL,
                                                account_id=account.account_id,
                                                order_type=OrderType.ORDER_TYPE_MARKET,
                                                order_id=unique_order_id,
                                            )
                                            logger.info(
                                                f"Ордер execution_report_status: {order.execution_report_status}"
                                            )
                                            if order.execution_report_status==1:
                                                order_request = SandboxPostOrderRequest.objects.create(
                                                    account_id=account,
                                                    instrument_id=instrument,
                                                    quantity=quantity_sum,
                                                    direction=OrderDirection.ORDER_DIRECTION_SELL,
                                                    order_type=OrderType.ORDER_TYPE_MARKET,
                                                    order_id=unique_order_id
                                                )
                                                logger.info(f"Ордер запрос: {order_request}")
                                                order_response = SandboxPostOrderResponse.objects.create(
                                                    order_response=order_request,
                                                    order_id=order.order_id,
                                                    order_request_id=order.order_request_id,
                                                    instrument_uid=order.instrument_uid,
                                                    figi=order.figi,
                                                    execution_report_status=order.execution_report_status,
                                                    direction=order.direction,
                                                    order_type=order.order_type,
                                                    lots_requested=order.lots_requested,
                                                    lots_executed=order.lots_executed,
                                                    initial_order_price=cast_to_decimal(order.initial_order_price),
                                                    executed_order_price=cast_to_decimal(order.executed_order_price),
                                                    total_order_amount=cast_to_decimal(order.total_order_amount),
                                                    initial_commission=cast_to_decimal(order.initial_commission),
                                                    executed_commission=cast_to_decimal(order.executed_commission),
                                                    aci_value=cast_to_decimal(order.aci_value),
                                                    initial_security_price=cast_to_decimal(order.initial_security_price),
                                                    initial_order_price_pt=cast_to_decimal(order.initial_order_price_pt),
                                                    message=order.message,
                                                    response_metadata=order.response_metadata,
                                                )
                                                logger.info(f"Ордер ответ сохранен: {order}")

                                            logger.info(f"Ордер: {order}")
                                            quantity_sum -= quantity_sum
                                    except RequestError as e:
                                        logger.error(
                                            f"Ошибка API T-Invest: {e.details if e.details else 'Неверные параметры или токен'}"
                                        )
                                        logger.error(
                                            f"Ошибка API: {e.metadata.message if e.metadata else str(e)}"
                                        )
                                        return redirect(
                                            "user:sandbox_detail",
                                            pk=account.pk,
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Критическая ошибка подключения: {e}"
                                        )
                                else:
                                    logger.error("Нет позиций для продажи.")
                            case "HOLD":
                                pass
                            case _:
                                print("")

                    self.stdout.write(
                        self.style.SUCCESS(
                            "Ожидание получения новых данных..."
                        )
                    )
                    time.sleep(5)

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Ошибка в цикле бота: {e}")
                    )
                    time.sleep(10)

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\nБот остановлен вручную (Ctrl+C).")
            )
        except SystemExit:
            pass
        finally:
            self.stdout.write(
                self.style.NOTICE("Обновляем статус бота в базе данных...")
            )
            BotConfiguration.objects.filter(id=config.id).update(
                is_active=False
            )
            self.stdout.write(
                self.style.SUCCESS("Статус бота в БД изменен на: Выключен")
            )
            self.stdout.write(self.style.SUCCESS("Бот успешно отключен."))
            logger.info(f"Бот завершил работу...{datetime.now()}")
