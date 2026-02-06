from utils.simple_logger import get_simple_logger
import os

_logger = None

def setup_logger(log_level=None):
    global _logger
    if _logger is not None:
        return _logger
    
    # Use simple logger to avoid circular dependencies
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    _logger = get_simple_logger("trading_bot", log_level)
    return _logger