import json
import time
import requests
from abc import ABC, abstractmethod
from utils.logging_setup import setup_logger


def _get_timestamp():
    """Получить текущее время в миллисекундах."""
    return str(int(time.time() * 1000))


class APIClient(ABC):
    def __init__(self, base_url, api_key, secret_key, passphrase=None):
        self.base_url = base_url
        self.api_key = api_key
        self.secret_key: str = secret_key
        self.passphrase = passphrase
        self.logger = setup_logger()

    @abstractmethod
    def _sign(self, message):
        """Сгенерировать подпись в зависимости от биржи."""
        pass

    @abstractmethod
    def _get_headers(self, timestamp, signature, method, body_str):
        """Сформировать заголовки (зависит от биржи)."""
        pass

    def _make_request(self, method, endpoint, params=None, body=None, max_retries=3, retry_delay=2):
        """
        Выполняет API запрос с обработкой сетевых ошибок и повторными попытками
        
        Args:
            method: HTTP метод (GET, POST)
            endpoint: API endpoint
            params: URL параметры
            body: Тело запроса
            max_retries: Максимальное количество попыток (по умолчанию 3)
            retry_delay: Задержка между попытками в секундах (по умолчанию 2)
            
        Returns:
            requests.Response: Объект ответа
            
        Raises:
            Exception: После исчерпания всех попыток
        """
        # Таймауты: (connect_timeout, read_timeout)
        timeout = (5, 30)
        
        timestamp = _get_timestamp()
        request_path = endpoint

        sorted_params = sorted(params.items()) if params else []
        query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
        request_path_with_query = f"{request_path}?{query_string}" if sorted_params else request_path

        body_str = json.dumps(body) if body else ""

        pre_hash_message = self._pre_hash(
            timestamp=timestamp,
            method=method,
            endpoint=request_path,  
            query_string=query_string, 
            body=body_str
        )

        signature = self._sign(pre_hash_message)
        headers = self._get_headers(timestamp, signature, method, body_str)
        url = self.base_url + request_path_with_query

        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Выполнение запроса с таймаутом
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method == "POST":
                    response = requests.post(url, headers=headers, data=body_str, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                return response
                
            except requests.exceptions.Timeout as e:
                last_error = e
                error_type = "Timeout"
                self.logger.error(
                    f"Timeout при запросе к {endpoint} (попытка {attempt + 1}/{max_retries}): {e}"
                )
                
            except requests.exceptions.ConnectionError as e:
                last_error = e
                error_type = "ConnectionError"
                self.logger.error(
                    f"Ошибка соединения с {endpoint} (попытка {attempt + 1}/{max_retries}): {e}"
                )
                
            except requests.exceptions.RequestException as e:
                last_error = e
                error_type = "RequestException"
                self.logger.error(
                    f"Ошибка запроса к {endpoint} (попытка {attempt + 1}/{max_retries}): {e}"
                )
            
            # Если это не последняя попытка - ждем перед повтором
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)  # Увеличиваем задержку с каждой попыткой
                self.logger.warning(
                    f"⏳ Повторная попытка через {wait_time} секунд..."
                )
                time.sleep(wait_time)
            else:
                # Последняя попытка не удалась
                self.logger.error(
                    f"Все {max_retries} попыток исчерпаны для {endpoint}. "
                    f"Последняя ошибка: {error_type}"
                )
        
        # Если все попытки не удались - пробрасываем исключение
        raise Exception(f"Network error after {max_retries} attempts: {last_error}")

    def _pre_hash(self, timestamp, method, endpoint, query_string, body):
        return f"{timestamp}{method.upper()}{endpoint}?{query_string}{body}"