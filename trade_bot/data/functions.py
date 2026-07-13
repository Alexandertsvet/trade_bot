import calendar
import json

import pandas as pd


def return_data_from_year(year: int):
    result = []
    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            result.append(f"{year}-{month:02d}-{day:02d}")

    return result


def return_two_element(iter_element: list):
    result = []
    for i in range(0, len(iter_element), 2):
        if i + 1 < len(iter_element):
            result.append((iter_element[i], iter_element[i + 1]))
        else:
            result.append((iter_element[i], iter_element[i]))
    return result


def df_to_lightweight_charts(df):
    df["tradetime"] = pd.to_datetime(df["tradetime"])
    df["time"] = df["tradetime"].astype("int64") // 10**9
    rename_dict = {
        "pr_open": "open",
        "pr_high": "high",
        "pr_low": "low",
        "pr_close": "close",
    }
    df_charts = df[
        ["time", "pr_open", "pr_high", "pr_low", "pr_close"]
    ].rename(columns=rename_dict)
    raw_data = df_charts.to_dict(orient="records")
    data = json.dumps(raw_data, indent=4)
    return data


def create_db(client, db_name, table_name):
    try:
        create_db_query = f"CREATE DATABASE IF NOT EXISTS {db_name}"
        client.execute(create_db_query)

        client.execute(f"USE {db_name}")
        print(f"База данных '{db_name}' успешно создана или уже существует")

        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {db_name}.{table_name} (
                tradedate Date,
                tradetime DateTime('Europe/Moscow'),
                secid String,
                pr_open Float64,
                pr_high Float64,
                pr_low Float64,
                pr_close Float64,
                pr_std Float64,
                vol Int32,
                val Float64,
                trades Int32,
                pr_vwap Float64,
                pr_change Float64,
                trades_b Int32,
                trades_s Int32,
                val_b Float64,
                val_s Float64,
                vol_b Int64,
                vol_s Int64,
                disb Float64,
                pr_vwap_b Nullable(Float64),
                pr_vwap_s Nullable(Float64),
                SYSTIME DateTime('Europe/Moscow'),
                sec_pr_open Nullable(Int32),
                sec_pr_high Nullable(Int32),
                sec_pr_low Nullable(Int32),
                sec_pr_close Nullable(Int32)
            )
            ENGINE = ReplacingMergeTree()
            ORDER BY (secid, tradedate, tradetime)
            """

        client.execute(create_table_query)
        print(f"Таблица '{table_name}' успешно создана в БД '{db_name}'")

        result = client.execute(f"DESCRIBE TABLE {table_name}")

        for row in result:
            print(f"  {row[0]}: {row[1]}")

    except Exception as e:
        print(f"Ошибка при создании БД/таблицы: {e}")
        return False
    finally:
        if "client" in locals():
            client.disconnect()


def return_data_from_year(year: int):
    result = []
    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            result.append(f"{year}-{month:02d}-{day:02d}")

    return result


def return_two_element(iter_element: list):

    result = []
    for i in range(0, len(iter_element), 2):
        if i + 1 < len(iter_element):
            result.append((iter_element[i], iter_element[i + 1]))
        else:
            result.append((iter_element[i], iter_element[i]))
    return result
