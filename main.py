import time
import uuid
from time import sleep
import config
from utils.logging_setup import setup_logger

logger = setup_logger()
from api.exchange_factory import ExchangeFactory
from trayding.risk_manager import RiskManager
from trayding.position_manager import PositionManager
from config import ExchangeConfig
from config import TelegramConfig
from api.bitget_connector import BitgetConnector
from datetime import datetime, timezone
import asyncio

def main():
    exchange = ExchangeFactory.create_connector("bitget", True)
    risk_manager = RiskManager(exchange,daily_loss_limit=ExchangeConfig.DAILY_LOSS_LIMIT)
    position_manager = PositionManager(exchange, risk_manager)

    # Проверка открытия позиции на споте
    # position = position_manager.open_position(
    #     symbol="BTCUSDT",
    #     side="buy",
    #     amount_type="fixed",ч
    #     order_type="market",
    #     market_type="spot",
    #     amount=100,
    #     product_type="USDT-SPOT"
    #     # price=price,
    #     # force=force
    # )
    # print(f"Открыта позиция: {position}")

    # Проверка открытие позиции на фьючах
    position = position_manager.open_position(
        symbol="BTCUSDT",
        side="buy",
        amount_type="fixed",
        amount=100,  # USDT
        order_type="market",
        market_type="futures",
        leverage=1,
        product_type="USDT-FUTURES",
        margin_coin="USDT",
        position_action = "open",
        margin_mode = "crossed"
    )
    logger.info(f"Открыта позиция: {position}")






if __name__ == "__main__":
    main()
