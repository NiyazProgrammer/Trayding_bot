from cachetools import TTLCache
from functools import wraps
import logging
from utils.logging_setup import setup_logger

logger = setup_logger()

price_cache = TTLCache(maxsize=100, ttl=5)
balance_cache = TTLCache(maxsize=10, ttl=10)

def cached(cache):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}_{args}_{kwargs}"
            if cache_key in cache:
                logger.info(f"Данные для {cache_key} взяты из кэша")
                return cache[cache_key]
            
            result = func(*args, **kwargs)
            if result and result.get('code') == '00000':
                cache[cache_key] = result
                logger.info(f"Данные для {cache_key} обновлены в кэше")
            return result
        return wrapper
    return decorator