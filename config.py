from dotenv import load_dotenv
import os
from utils.logging_setup import setup_logger

logger = setup_logger()

class TelegramConfig:
    BOT_TOKEN = os.getenv("BOT_TOKEN")

class ExchangeConfig:

    # Очищение переменных окружений
    os.environ.pop("BITGET_API_KEY", None)
    os.environ.pop("BITGET_SECRET_KEY", None)
    os.environ.pop("BITGET_PASSPHRASE", None)

    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if load_dotenv(dotenv_path):
        logger.info("Файл .env успешно загружен")
    else:
        logger.error("Не удалось загрузить файл .env")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    MAX_POSITION_SIZE = 0.2
    QUANTITY_PRECISION = 6

    # Точность количества для разных торговых пар
    QUANTITY_PRECISION_MAP = {
        "BTC": 4,
        "ETH": 3,
        "BNB": 2,
        "SOL": 2,
        "ADA": 0,
        "LTC": 1,
        "AVAX": 1,
        "MATIC": 0,
        "XRP": 0,
        "DOGE": 0,
        "SHIB": 0,
        "TRX": 0,
    }
    DEFAULT_QUANTITY_PRECISION = 2

    MIN_USER_POSITION_PERCENTAGE = 0.05
    MAX_USER_POSITION_PERCENTAGE = 0.20
    DAILY_LOSS_LIMIT = 50

    COMMISSION_RATES = {
        "spot": {
            "maker": float(os.getenv("SPOT_MAKER_FEE", 0.001)),  # 0.1%
            "taker": float(os.getenv("SPOT_TAKER_FEE", 0.001)),  # 0.1%
        },
        "futures": {
            "maker": float(os.getenv("FUTURES_MAKER_FEE", 0.0002)),  # 0.02%
            "taker": float(os.getenv("FUTURES_TAKER_FEE", 0.0006)),  # 0.06%
        }
    }

    BITGET_CONFIG = {
        "base_url": "https://api.bitget.com",
        "api_key": os.getenv("BITGET_API_KEY"),
        "secret_key": os.getenv("BITGET_SECRET_KEY"),
        "passphrase": os.getenv("BITGET_PASSPHRASE"),
        "cache_ttl": 5,
    }
    
    BITGET_DEMO_CONFIG = {
        "base_url": "https://api.bitget.com",
        "api_key": os.getenv("BITGET_DEMO_API_KEY"),
        "secret_key": os.getenv("BITGET_DEMO_SECRET_KEY"),
        "passphrase": os.getenv("BITGET_DEMO_PASSPHRASE"),
        "cache_ttl": 5,
    }