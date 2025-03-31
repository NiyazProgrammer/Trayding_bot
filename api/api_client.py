import json
import time
import requests
from abc import ABC, abstractmethod
from utils.error_handling import retry_on_failure
from utils.logging_setup import setup_logger

class APIClient(ABC):
    def __init__(self, base_url, api_key, secret_key, passphrase=None):
        self.base_url = base_url
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.logger = setup_logger()

    def _get_timestamp(self):
        """Получить текущее время в миллисекундах."""
        return str(int(time.time() * 1000))

    @abstractmethod
    def _sign(self, message):
        """Сгенерировать подпись в зависимости от биржи."""
        pass

    @abstractmethod
    def _get_headers(self, timestamp, signature, method, body_str):
        """Сформировать заголовки (зависит от биржи)."""
        pass

    @retry_on_failure(max_retries=3, delay=1)
    def _make_request(self, method, endpoint, params=None, body=None):
        timestamp = self._get_timestamp()
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

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body_str)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise Exception(f"API request failed: {e}")

    def _pre_hash(self, timestamp, method, endpoint, query_string, body):
        return f"{timestamp}{method.upper()}{endpoint}?{query_string}{body}"