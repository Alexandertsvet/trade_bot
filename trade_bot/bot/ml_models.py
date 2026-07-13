import json

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from prophet.serialize import model_from_json, model_to_json
from statsmodels.tsa.statespace.sarimax import SARIMAX


class RealTimeForecaster:
    def __init__(self, p=3, q=2):
        self.p = p
        self.q = q

    def predict_on_dataframe(self, df_window):
        """
        Принимает готовый DataFrame из ClickHouse (колонки 'tradetime' и 'pr_close')
        """
        df_ticker = df_window[["tradetime", "pr_close"]].rename(
            columns={"tradetime": "ds", "pr_close": "y"}
        )
        df_ticker["ds"] = pd.to_datetime(df_ticker["ds"]).dt.tz_localize(None)

        if len(df_ticker) < max(self.p, self.q) + 10:
            return None

        try:
            # Обучаем ARMA на данных (d=1)
            model = SARIMAX(
                df_ticker["y"],
                order=(self.p, 1, self.q),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            model_fitted = model.fit(disp=False)

            # Быстрый точечный прогноз на 3 шага вперед
            return_pred = model_fitted.forecast(steps=3)

            # Генерация временной сетки MoEX
            predictions = self._generate_future_timestamps(
                last_time=df_ticker["ds"].iloc[-1], values=return_pred
            )
            return predictions

        except Exception as e:
            print(f"Ошибка в расчете ARIMA: {e}")
            return None

    def _generate_future_timestamps(self, last_time, values):
        """
        Генерирует сетку времени MoEX без ночи и выходных
        """
        future_times = pd.date_range(
            start=last_time + pd.Timedelta(minutes=5), periods=50, freq="5min"
        )

        start_session = pd.to_datetime("06:50:00").time()
        end_session = pd.to_datetime("23:50:00").time()
        valid_times = future_times[
            (future_times.time >= start_session)
            & (future_times.time <= end_session)
        ]

        valid_times = valid_times[
            ~(
                (valid_times.time > pd.to_datetime("18:50:00").time())
                & (valid_times.time < pd.to_datetime("19:00:00").time())
            )
        ]

        # Возвращаем только чистые log returns
        return pd.DataFrame(
            {
                "tradetime": valid_times[:3],
                "horizon": ["5", "10", "15"],
                "return_pred": np.round(values, 6),
            }
        )


# ==========================================
# 1. НА СЕРВЕРЕ ОБУЧЕНИЯ (Запускается, например, раз в неделю)
# ==========================================
def save_trained_model(model, filepath="prophet_model.json"):
    """Конвертирует модель Prophet в формат JSON и сохраняет на диск."""
    with open(filepath, "w") as f:
        # model_to_json превращает веса и параметры модели в строку
        json.dump(model_to_json(model), f)
    print(f"Успешно! Модель сохранена в файл: {filepath}")


# ==========================================
# 2. В ТОРГОВОМ РОБОТЕ (Запускается утром перед открытием биржи)
# ==========================================
def load_trained_model(filepath="prophet_model.json"):
    """Загружает модель из файла JSON без необходимости доступа к истории."""
    with open(filepath, "r") as f:
        model_str = json.load(f)
        # Восстанавливаем полноценный объект Prophet из строки
        model = model_from_json(model_str)
    print("Успешно! Модель загружена и готова к прогнозированию.")
    return model


class RealTimeProphetForecaster:
    def __init__(self, model_json_path):
        """Принимает путь к сохраненной модели JSON"""
        with open(model_json_path, "r", encoding="utf-8") as f:
            self.model = model_from_json(json.load(f))

    def _add_session_features(self, df):
        """Внутренний метод разметки сессий MoEX для векторов Prophet"""
        df = df.copy()
        times = pd.to_datetime(df["ds"]).dt.time

        df["morning_session"] = (
            (times >= pd.to_datetime("06:50:00").time())
            & (times < pd.to_datetime("10:00:00").time())
        ).astype(int)
        df["main_session"] = (
            (times >= pd.to_datetime("10:00:00").time())
            & (times < pd.to_datetime("19:00:00").time())
        ).astype(int)
        df["evening_session"] = (
            (times >= pd.to_datetime("19:00:00").time())
            & (times <= pd.to_datetime("23:50:00").time())
        ).astype(int)
        return df

    def predict_on_dataframe(self, df_window):
        """
        Принимает DataFrame из ClickHouse (колонки 'tradetime' и 'pr_close')
        """
        # Преобразование под формат модели и очистка от таймзон
        df_ticker = df_window[["tradetime", "pr_close"]].rename(
            columns={"tradetime": "ds", "pr_close": "y"}
        )
        df_ticker["ds"] = pd.to_datetime(df_ticker["ds"]).dt.tz_localize(None)

        if len(df_ticker) < 1:
            return None

        last_time = df_ticker["ds"].iloc[-1]
        actual_price = df_ticker["y"].iloc[-1]

        try:
            # 1. Генерируем временную сетку MoEX без ночи/выходных/клирингов
            valid_times = self._generate_future_timestamps(last_time)

            # Собираем DataFrame: текущая точка (для калибровки) + 3 будущие точки
            future_ds = pd.concat(
                [pd.Series([last_time]), pd.Series(valid_times[:3])]
            ).reset_index(drop=True)
            future_df = pd.DataFrame({"ds": future_ds})

            # КРИТИЧЕСКИЙ ШАГ: Добавляем признаки сессий, иначе model.predict() вызовет ValueError
            future_ready = self._add_session_features(future_df)

            # 2. Быстрый инференс базовой модели
            raw_forecast = self.model.predict(future_ready)

            # Извлекаем сырое ожидание модели на текущий момент времени
            expected_now = raw_forecast.loc[
                raw_forecast["ds"] == last_time, "yhat"
            ].values[0]

            # Расчет сдвига текущей итерации в логарифмах
            gap_shift = actual_price - expected_now

            # 3. Применяем сдвиг ко всей сетке в логарифмах
            raw_forecast["yhat"] += gap_shift
            raw_forecast["yhat_lower"] += gap_shift
            raw_forecast["yhat_upper"] += gap_shift
            future_predictions = raw_forecast.tail(3).reset_index(drop=True)

            return pd.DataFrame(
                {
                    "tradetime": valid_times[:3],
                    "horizon": ["5", "10", "15"],
                    "return_pred": future_predictions["yhat"].values,
                }
            )

        except Exception as e:
            print(f"Ошибка в расчете Prophet: {e}")
            return None

    def _generate_future_timestamps(self, last_time):
        """Генерирует правильную сетку времени MoEX, полностью исключая ночь и выходные"""
        future_times = pd.date_range(
            start=last_time + pd.Timedelta(minutes=5), periods=50, freq="5min"
        )

        start_session = pd.to_datetime("06:50:00").time()
        end_session = pd.to_datetime("23:50:00").time()
        valid_times = future_times[
            (future_times.time >= start_session)
            & (future_times.time <= end_session)
        ]

        valid_times = valid_times[
            ~(
                (valid_times.time > pd.to_datetime("18:50:00").time())
                & (valid_times.time < pd.to_datetime("19:00:00").time())
            )
        ]
        return valid_times.to_series().reset_index(drop=True)


class RealTimeCatBoostForecaster:
    def __init__(self, path_5m, path_10m, path_15m):
        """Загрузка трех предобученных моделей CatBoost"""
        self.model_5m = CatBoostRegressor().load_model(path_5m)
        self.model_10m = CatBoostRegressor().load_model(path_10m)
        self.model_15m = CatBoostRegressor().load_model(path_15m)

        # Набор признаков в строго определенном порядке (как при обучении)
        self.feature_cols = [
            "pr_std",
            "vol",
            "val",
            "trades",
            "pr_vwap",
            "pr_change",
            "trades_b",
            "trades_s",
            "val_b",
            "val_s",
            "vol_b",
            "vol_s",
            "disb",
            "pr_vwap_b",
            "pr_vwap_s",
            "hour",
            "minute",
            "dayofweek",
            "morning_session",
            "main_session",
            "evening_session",
            "spread",
            "vol_ratio",
            "val_ratio",
            "vwap_spread",
            "current_price",
            "lag_5m",
            "lag_10m",
            "lag_15m",
            "sma_fast",
            "sma_slow",
            "dist_fast",
            "dist_slow",
            "sma_diff",
        ]

    def _extract_features(self, df_window):
        """
        Полностью воспроизводит логику preprocessing_data для последней точки.
        На вход подается окно из ClickHouse (минимум 12 строк для расчета sma_slow).
        """
        df = df_window.copy(deep=True)
        df = df.sort_values("tradetime").reset_index(drop=True)

        # Приведение к datetime без таймзон
        df["tradetime"] = pd.to_datetime(df["tradetime"]).dt.tz_localize(None)

        # Календарные фичи
        df["hour"] = df["tradetime"].dt.hour
        df["minute"] = df["tradetime"].dt.minute
        df["dayofweek"] = df["tradetime"].dt.dayofweek

        # Разметка сессий MoEX
        times = df["tradetime"].dt.time
        morning_start = pd.to_datetime("06:50:00").time()
        main_start = pd.to_datetime("10:00:00").time()
        evening_start = pd.to_datetime("19:00:00").time()
        evening_end = pd.to_datetime("23:50:00").time()

        df["morning_session"] = (
            (times >= morning_start) & (times < main_start)
        ).astype(int)
        df["main_session"] = (
            (times >= main_start) & (times < evening_start)
        ).astype(int)
        df["evening_session"] = (
            (times >= evening_start) & (times <= evening_end)
        ).astype(int)

        # Рыночные микроструктурные фичи
        df["spread"] = (df["pr_high"] - df["pr_low"]) / df["pr_close"]
        df["vol_ratio"] = df["vol_b"] / df["vol_s"]
        df["val_ratio"] = df["val_b"] / df["val_s"]
        df["vwap_spread"] = (df["pr_vwap_b"] - df["pr_vwap_s"]) / df[
            "pr_close"
        ]

        # Цены и лаги
        df["current_price"] = df["pr_close"]
        df["lag_5m"] = df["pr_close"].shift(1)
        df["lag_10m"] = df["pr_close"].shift(2)
        df["lag_15m"] = df["pr_close"].shift(3)

        # Скользящие средние (SMA)
        df["sma_fast"] = df["pr_close"].rolling(window=5).mean()
        df["sma_slow"] = df["pr_close"].rolling(window=12).mean()

        # Производные фичи от средних
        df["dist_fast"] = df["pr_close"] / df["sma_fast"] - 1
        df["dist_slow"] = df["pr_close"] / df["sma_slow"] - 1
        df["sma_diff"] = df["sma_fast"] / df["sma_slow"] - 1

        # Извлекаем СТРОГО последнюю строку (текущий момент времени),
        # где полностью рассчитались все лаги и SMA(12)
        last_row_features = (
            df[self.feature_cols].tail(1).reset_index(drop=True)
        )

        return last_row_features

    def predict_on_dataframe(self, df_window):
        """
        Принимает DataFrame из ClickHouse (минимум 12 последних баров).
        Возвращает DataFrame с предсказанием цен на 3 шага вперед.
        """
        # Нам нужно как минимум 12 строк для корректного расчета 'sma_slow'
        if len(df_window) < 12:
            print(
                "Ошибка: Для расчета фичей требуется окно как минимум из 12 строк."
            )
            return None

        try:
            # Сортируем и определяем время последней известной точки
            df_window = df_window.copy()
            df_window["tradetime"] = pd.to_datetime(
                df_window["tradetime"]
            ).dt.tz_localize(None)
            df_window = df_window.sort_values("tradetime").reset_index(
                drop=True
            )
            last_time = df_window["tradetime"].iloc[-1]

            # 1. Генерируем временную сетку MoEX для вывода результатов
            valid_times = self._generate_future_timestamps(last_time)

            # 2. Выделяем вектор признаков (X) строго под формат CatBoost
            X = self._extract_features(df_window)

            # 3. Быстрый инференс моделей
            pred_5m = self.model_5m.predict(X)[0]
            pred_10m = self.model_10m.predict(X)[0]
            pred_15m = self.model_15m.predict(X)[0]

            # Формируем результат
            return pd.DataFrame(
                {
                    "tradetime": valid_times[:3],
                    "horizon": ["5", "10", "15"],
                    "return_pred": [pred_5m, pred_10m, pred_15m],
                }
            )

        except Exception as e:
            print(f"Ошибка при расчете прогноза CatBoost: {e}")
            return None

    def _generate_future_timestamps(self, last_time):
        """Генерирует правильную сетку времени MoEX без ночи и клирингов"""
        future_times = pd.date_range(
            start=last_time + pd.Timedelta(minutes=5), periods=50, freq="5min"
        )
        start_session, end_session = (
            pd.to_datetime("06:50:00").time(),
            pd.to_datetime("23:50:00").time(),
        )
        valid_times = future_times[
            (future_times.time >= start_session)
            & (future_times.time <= end_session)
        ]
        valid_times = valid_times[
            ~(
                (valid_times.time > pd.to_datetime("18:50:00").time())
                & (valid_times.time < pd.to_datetime("19:00:00").time())
            )
        ]
        return valid_times.to_series().reset_index(drop=True)


class RealTimeMetaEnsemble:
    def __init__(self, prophet_path, cb_paths, meta_classifier_path):
        """
        Управляющий класс мета-ансамбля (Стекинг 2-го уровня).

        prophet_path: путь к json-файлу базовой модели Prophet
        cb_paths: словарь путей к базовым CatBoost {'5': path, '10': path, '15': path}
        meta_classifier_path: путь к обученной единой метамодели-классификатору
        """
        # 1. Инициализируем базовые инференс-классы (1 уровень)
        self.arima_forecaster = RealTimeForecaster(p=3, q=2)
        self.prophet_forecaster = RealTimeProphetForecaster(prophet_path)
        self.catboost_forecaster = RealTimeCatBoostForecaster(
            cb_paths["5"], cb_paths["10"], cb_paths["15"]
        )

        # 2. Загружаем единую метамодель классификации (2 уровень)
        self.meta_classifier = CatBoostClassifier().load_model(
            meta_classifier_path
        )

        # Строгий порядок колонок-признаков для мета-классификатора (должен совпадать с обучением)
        self.meta_feature_cols = [
            "arima_p5",
            "arima_p10",
            "arima_p15",
            "prophet_p5",
            "prophet_p10",
            "prophet_p15",
            "catboost_p5",
            "catboost_p10",
            "catboost_p15",
            "arima_err_5m",
            "arima_err_10m",
            "arima_err_15m",
            "prophet_err_5m",
            "prophet_err_10m",
            "prophet_err_15m",
            "catboost_err_5m",
            "catboost_err_10m",
            "catboost_err_15m",
            "current_price",
            "spread",
            "vol_ratio",
            "val_ratio",
            "vwap_spread",
            "sma_diff",
            "dist_fast",
            "dist_slow",
            "hour",
            "minute",
        ]

        # Карта перевода числовых выходов классификатора в торговые приказы
        self.signal_map = {0: "SELL", 1: "HOLD", 2: "BUY"}

        # Внутренний оперативный буфер памяти для расчета скользящих ошибок прошлого
        # Структура: {timestamp: {'arima': [p5, p10, p15], 'prophet': [...], 'catboost': [...]}}
        self.predictions_history = {}

    def _calculate_rolling_errors(self, last_time, price_now):
        """
        Внутренний метод: находит в памяти прогнозы, сделанные 5, 10 и 15 минут назад
        под ТЕКУЩИЙ момент времени, и вычисляет чистую ошибку алгоритмов.
        """
        # Вычисляем временные метки "прошлого"
        t_5 = last_time - pd.Timedelta(minutes=5)
        t_10 = last_time - pd.Timedelta(minutes=10)
        t_15 = last_time - pd.Timedelta(minutes=15)

        errs = {}
        for algo in ["arima", "prophet", "catboost"]:
            # Извлекаем то точечное предсказание, которое делалось назад во времени под текущую минуту
            # Индексы массивов: [0] = прогноз на +5м, [1] = прогноз на +10м, [2] = прогноз на +15м
            pred_5m_ago = self.predictions_history.get(t_5, {}).get(
                algo, [price_now, price_now, price_now]
            )[0]
            pred_10m_ago = self.predictions_history.get(t_10, {}).get(
                algo, [price_now, price_now, price_now]
            )[1]
            pred_15m_ago = self.predictions_history.get(t_15, {}).get(
                algo, [price_now, price_now, price_now]
            )[2]

            # Ошибка = Реальность сейчас - То, что прогнозировали в прошлом под этот момент
            errs[f"{algo}_err_5m"] = price_now - pred_5m_ago
            errs[f"{algo}_err_10m"] = price_now - pred_10m_ago
            errs[f"{algo}_err_15m"] = price_now - pred_15m_ago

        # Защита от утечки ОЗУ: очищаем буфер от записей старше 15 минут
        self.predictions_history = {
            k: v for k, v in self.predictions_history.items() if k >= t_15
        }

        return errs

    def predict_trade_signal(self, df_window):
        """
        Главный метод инференса реального времени.
        Принимает скользящее окно из ClickHouse.
        Возвращает словарь с финальным торговым решением и скором уверенности.
        """
        if len(df_window) < 12:
            print(
                "Ошибка ансамбля: Окно данных из ClickHouse должно быть не менее 12 строк."
            )
            return None

        # Стандартизация фрейма
        df_window = df_window.copy()
        df_window["tradetime"] = pd.to_datetime(
            df_window["tradetime"]
        ).dt.tz_localize(None)
        df_window = df_window.sort_values("tradetime").reset_index(drop=True)

        last_time = df_window["tradetime"].iloc[-1]
        price_now = df_window["pr_close"].iloc[-1]

        try:
            # 1. ОПРОС БАЗОВЫХ МОДЕЛЕЙ (1 уровень)
            res_arima = self.arima_forecaster.predict_on_dataframe(df_window)
            res_prophet = self.prophet_forecaster.predict_on_dataframe(
                df_window
            )
            res_cb = self.catboost_forecaster.predict_on_dataframe(df_window)

            # Извлекаем массивы предсказаний [pred_5m, pred_10m, pred_15m]
            arima_pred = (
                res_arima["return_pred"].values
                if res_arima is not None
                else [price_now] * 3
            )
            prophet_pred = (
                res_prophet["return_pred"].values
                if res_prophet is not None
                else [price_now] * 3
            )
            cb_pred = (
                res_cb["return_pred"].values
                if res_cb is not None
                else [price_now] * 3
            )

            # 2. РАСЧЕТ ИСТОРИЧЕСКИХ ОШЕБОК (Через локальный буфер)
            errs_dict = self._calculate_rolling_errors(last_time, price_now)

            # 3. СОХРАНЕНИЕ ТЕКУЩИХ ПРОГНОЗОВ (Для следующих шагов инференса)
            self.predictions_history[last_time] = {
                "arima": arima_pred,
                "prophet": prophet_pred,
                "catboost": cb_pred,
            }

            # 4. ИЗВЛЕЧЕНИЕ РЫНОЧНОГО КОНТЕКСТА
            # Забираем рассчитанные технические/стаканные фичи из экстрактора базового CatBoost
            X_cb_context = self.catboost_forecaster._extract_features(
                df_window
            )

            # 5. СБОРКА ЕДИНОГО ВЕКТОРА ПРИЗНАКОВ ДЛЯ МЕТА-КЛАССИФИКАТОРА
            meta_input = pd.DataFrame(
                [
                    {
                        # Базовые прогнозы
                        "arima_p5": arima_pred[0],
                        "arima_p10": arima_pred[1],
                        "arima_p15": arima_pred[2],
                        "prophet_p5": prophet_pred[0],
                        "prophet_p10": prophet_pred[1],
                        "prophet_p15": prophet_pred[2],
                        "catboost_p5": cb_pred[0],
                        "catboost_p10": cb_pred[1],
                        "catboost_p15": cb_pred[2],
                        # Распаковываем посчитанные ошибки прошлого
                        **errs_dict,
                        # Рыночные контекстные признаки
                        "current_price": price_now,
                        "spread": X_cb_context["spread"].iloc[0],
                        "vol_ratio": X_cb_context["vol_ratio"].iloc[0],
                        "val_ratio": X_cb_context["val_ratio"].iloc[0],
                        "vwap_spread": X_cb_context["vwap_spread"].iloc[0],
                        "sma_diff": X_cb_context["sma_diff"].iloc[0],
                        "dist_fast": X_cb_context["dist_fast"].iloc[0],
                        "dist_slow": X_cb_context["dist_slow"].iloc[0],
                        "hour": int(X_cb_context["hour"].iloc[0]),
                        "minute": int(X_cb_context["minute"].iloc[0]),
                    }
                ]
            )

            # Выстраиваем признаки в строгом соответствии с матрицей обучения
            X_meta = meta_input[self.meta_feature_cols]

            # 6. ИНФЕРЕНС МЕТА-КЛАССИФИКАТОРА (2 уровень)
            predicted_class = self.meta_classifier.predict(X_meta)[0][0]
            probabilities = self.meta_classifier.predict_proba(X_meta)[
                0
            ]  # Массив [prob_sell, prob_hold, prob_buy]

            return {
                "tradetime": last_time,
                "current_price": price_now,
                "signal": self.signal_map[predicted_class],
                "confidence": np.max(
                    probabilities
                ),  # Уверенность в выбранном классе
                "prob_sell": np.round(probabilities[0], 4),
                "prob_hold": np.round(probabilities[1], 4),
                "prob_buy": np.round(probabilities[2], 4),
            }

        except Exception as e:
            print(f"Критический сбой внутри RealTimeMetaEnsemble: {e}")
            return None
