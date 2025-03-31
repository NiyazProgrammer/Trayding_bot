import logging
from config import ExchangeConfig

_logger = None

def setup_logger():
    global _logger
    if _logger is not None:
        return _logger  

    logger = logging.getLogger("trading_bot")
    logger.setLevel(ExchangeConfig.LOG_LEVEL) 

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler("trading_bot.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)
    
    _logger = logger 
    return logger