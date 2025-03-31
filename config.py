from dotenv import load_dotenv
import os

class ExchangeConfig:
    # Очищение переменных окружений
    os.environ.pop("BITGET_API_KEY", None)
    os.environ.pop("BITGET_SECRET_KEY", None)
    os.environ.pop("BITGET_PASSPHRASE", None)

    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if load_dotenv(dotenv_path):
        print("Файл .env успешно загружен")
    else:
        print("Не удалось загрузить файл .env")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", 0.001))
    MAX_POSITION_SIZE = 0.2
    QUANTITY_PRECISION = 6
    MIN_USER_POSITION_PERCENTAGE = 0.05
    MAX_USER_POSITION_PERCENTAGE = 0.20

    BITGET_CONFIG = {
        "base_url": "https://api.bitget.com",
        "api_key": os.getenv("BITGET_API_KEY"),
        "secret_key": os.getenv("BITGET_SECRET_KEY"),
        "passphrase": os.getenv("BITGET_PASSPHRASE"),
        "cache_ttl": 5,
    }