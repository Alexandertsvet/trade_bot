# trade_bot
trade_bot

Работа через t invest API, и algopack api

.env file
# --- Django Settings ---
SECRET_KEY=...you django_key
SALT_KEY=...you api key
TINKOFF_TOKEN_SANDBOX=...you api key
DOCKER_ENV=True

# --- Integrations ---
ALGOPACK_KEY=Bearer ...you api key

# --- Redis ---
REDIS_URL=redis://redis:6379/0

# --- PostgreSQL ---
pg_db_name=trade_bor
pg_user=trade_bor_user
pg_password=postgres
pg_host=postgres
pg_port=5432

# --- ClickHouse ---
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=default
# ---            ---

Последовательность команд

модели находятся в папке: trade_bot/bot/ml_models
список моделей (catboost_model_5.cbm, catboost_model_10.cbm, catboost_model_15.cbm, unified_meta_classifier.cbm, prophet_model.json)
обучение моделей informations/ansambl.ipynb

docker compose up -d --build

docker exec trade_bot-web-1 python manage.py makemigrations

docker exec trade_bot-web-1 python3 manage.py create_db

Создание через веб интерфейс аккаунта (один аккаунта t invest API, один пользователь user)
http://127.0.0.1:8000/t_invest/accaunt/add/


python3 manage.py download_history --secid gazp --from 2026 --till 2026

docker exec trade_bot-web-1 python3 manage.py load_fin_instrument
загрузка инструмкентов доступных для торговли


docker exec trade_bot-web-1 python3 manage.py run_bot 1 1
запуск торгового бота

