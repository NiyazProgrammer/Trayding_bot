from functools import wraps
import time
from utils.logging_setup import setup_logger

# Настройка логгера
logger = setup_logger()

def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    logger.error(f"Ошибка: {e}. Повторная попытка {retries}/{max_retries}")
                    time.sleep(delay)
            logger.error("Превышено количество попыток")
            raise Exception("Превышено количество попыток")
        return wrapper
    return decorator