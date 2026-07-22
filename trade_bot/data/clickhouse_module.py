import os

from clickhouse_driver import Client
from dotenv import load_dotenv

load_dotenv()
Authorization = os.getenv("Authorization")
headers = {
    "Accept": "application/json",
    "Authorization": Authorization,
}
payload = {}

IS_DOCKER = os.getenv("DOCKER_ENV", "False").lower() in ("true", "1", "t")
print(f"Запущено в Docker: {IS_DOCKER}")

if IS_DOCKER:
    # В Docker контейнере
    CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST")
    CLICKHOUSE_PORT = os.getenv("CLICKHOUSE_PORT")
    CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER")
    CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD")
else:
    CLICKHOUSE_HOST = "localhost"
    CLICKHOUSE_PORT = 9000
    CLICKHOUSE_USER = "default"
    CLICKHOUSE_PASSWORD = "default"


class ClickHouseProcessor(Client):
    def __init__(self, host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT):
        super().__init__(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
        )

    def drop(self, table_name):
        """db.table"""
        query = f"""
        DROP TABLE IF EXISTS {table_name}
        """
        try:
            self.execute(query)
            logging.error(e)(f"удаление таблицы {table_name}")
        except Exception as e:
            logging.error(e)(f"error: {e}, при удаление таблицы {table_name}")

    def truncate_table(self, db, table_name):

        query = f"""
        TRUNCATE TABLE IF EXISTS {db}.{table_name}
        """
        try:
            self.execute(query)
            logging.error(e)(
                f"выполнена очистка данных таблицы {db}.{table_name}"
            )
        except Exception as e:
            logging.error(e)(
                f"error: {e}, при очистки таблицы {db}.{table_name}"
            )

    def get_report(self, limit=100, table="test_tradestats"):
        """
        Возвращает отчет о последних выполненных запросах из системного лога.
        Требует прав доступа к таблице system.query_log.
        """
        report_sql = f"""
        SELECT 
            event_time,
            query, 
            query_duration_ms / 1000 AS seconds, 
            read_rows, 
            formatReadableSize(read_bytes) AS memory
        FROM system.query_log
        WHERE query LIKE '%{table}%' AND type = 'QueryFinish' AND query NOT LIKE '%system.query_log%' 
        ORDER BY event_time DESC
        LIMIT {limit}
        """
        return self.query_dataframe(report_sql)

    def drop_duplicated(self, db, table="test_tradestats"):
        """
        Удаление дубликатов в таблице
        """

        return self.execute(f"OPTIMIZE TABLE {db}.{table} FINAL")

    # =============================================================================================
    def sql_limit_select_all_secid(self, db, table_name, limit: int, interval):
        """
        Берем только последние limit строк каждого поледнего secid
        во временном интервале от текушей даты (день)
        """

        query = f"""
                SELECT *
                FROM 
                (SELECT secid, tradetime, pr_close
                FROM {db}.{table_name}
                WHERE tradetime >= today() - INTERVAL {interval} DAY
                ORDER BY secid, tradetime DESC
                LIMIT {limit} by secid
                )
                ORDER BY secid, tradetime
                """
        return self.query

    def sql_limit_secid(
        self, secid: str, db: str, table_name: str, limit: int, interval: int
    ):
        """
        Берем только последние limit строк выбранного secid
        во временном интервале (день - int) от текушей даты (день)

        """

        query = f"""
                    SELECT *
                    FROM 
                    (SELECT secid, tradetime, pr_close
                    FROM {db}.{table_name}
                    PREWHERE secid = '{secid}' AND tradetime >= today() - INTERVAL {interval} DAY
                    ORDER BY tradetime DESC
                    LIMIT {limit} 
                    )
                    ORDER BY  tradetime
                    """
        return self.query_dataframe(query)

    def get_latest_window(self, secid="GAZP", window_size=200):
        sql = f"""
        SELECT *
        FROM (
            SELECT tradetime,
                    pr_open,
                    pr_high,
                    pr_low,
                    pr_close,
                    pr_std,
                    vol,
                    val,
                    trades,
                    pr_vwap,
                    pr_change,
                    trades_b,
                    trades_s, 
                    val_b,
                    val_s,
                    vol_b, 
                    vol_s, disb,
                    pr_vwap_b,
                    pr_vwap_s
            FROM test_trade.test_tradestats
            WHERE secid = '{secid}' AND tradetime >= today() - INTERVAL 3 DAY
            ORDER BY tradetime DESC
            LIMIT {window_size}
        )
        ORDER BY tradetime ASC
        """
        return self.query_dataframe(
            sql,
            settings={
                "optimize_read_in_order": 1,
                "max_block_size": window_size,
            },
        )

    def get_last_time(self, secid="GAZP"):
        sql = f"""
            SELECT
                max(tradetime)
            FROM test_trade.test_tradestats
            WHERE secid = '{secid}'
            """
        return self.execute(sql)
