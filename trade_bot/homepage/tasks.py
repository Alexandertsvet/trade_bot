from celery import shared_task
import time
import requests

@shared_task
def add_numbers(x, y):
    """Простая задача на сложение"""
    return x + y


@shared_task
def get_data_moex_index(index:str):
    try:
        url = f"https://iss.moex.com/iss/engines/stock/markets/index/securities/{index}.json"



        params = {
            'iss.meta': 'off',
           
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  
        
        data = response.json()
        
        securities_data = data.get('marketdata', {})
        columns = securities_data.get("columns", {})
        data = securities_data.get("data", {})[0]
        securities_data = tuple(zip(columns, data))
        
        if securities_data:
        
            return {"status": "SUCCESS", "data": securities_data}
            
        return {"status": "PROGRESS", "data": ""}
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Мосбирже: {e}")
        return {"status": "ERROR", "error": f"{e}"}
    except (KeyError, IndexError, ValueError) as e:
        print(f"Ошибка парсинга данных: {e}")
        return {"status": "ERROR", "error": f"{e}"}