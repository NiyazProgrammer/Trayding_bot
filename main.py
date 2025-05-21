import time
import uuid
from api.exchange_factory import ExchangeFactory
from trayding.risk_manager import RiskManager
from trayding.position_manager import PositionManager
from config import TelegramConfig
import telebot
from api.bitget_connector import BitgetConnector

def main():
    exchange = ExchangeFactory.create_connector("bitget", True)
    risk_manager = RiskManager(exchange)
    position_manager = PositionManager(exchange, risk_manager)

    # # 4. Проверка открытия позиции на споте
    # position = position_manager.open_position(
    #     symbol="BTCUSDT",
    #     side="buy",
    #     amount_type="fixed",
    #     order_type="market",
    #     market_type="spot",
    #     amount=100,
    #     product_type="USDT-SPOT"
    #     # price=price,
    #     # force=force
    # )
    # print(f"Открыта позиция: {position}")

    # Проверка открытие позиции на фьючах
    # position = position_manager.open_position(
    #     symbol="BTCUSDT",
    #     side="buy",
    #     amount_type="fixed",
    #     amount=50,  # USDT
    #     order_type="market",
    #     market_type="futures",
    #     leverage=10,
    #     product_type="USDT-FUTURES",
    #     margin_coin="USDT",
    #     position_action = "open",
    #     margin_mode = "crossed"
    # )
    # print(f"Открыта позиция: {position}")

    # Проверка Стоплосса
    # stop_loss_order_fix = position_manager.set_stop_loss(
    #     symbol="BTCUSDT",
    #     entry_price=42000,
    #     quantity=0.001,
    #     stop_loss_price=39000,
    #     side="buy"
    # )
    # print("Фиксированный стоплосс установлен:", stop_loss_order_fix)
    # stop_loss_order_dynamic = position_manager.set_stop_loss(
    #     symbol="BTCUSDT",
    #     entry_price=42000,
    #     quantity=0.001,
    #     stop_loss_percent=0.10,
    #     side="buy"
    # )
    # print("Динамический стоплосс установлен:", stop_loss_order_dynamic)

    # Проверка Тейк профита
    # result_take_profit_fix = position_manager.set_take_profit(
    #     symbol="BTCUSDT",
    #     entry_price=106000,
    #     quantity=0.002,
    #     tp_price=105800,
    #     side="sell"
    # )
    # print("Фиксированный тейк профит установелн:", result_take_profit_fix)
    # result_take_profit = position_manager.set_take_profit(
    #     symbol="BTCUSDT",
    #     entry_price=42000,
    #     quantity=0.001,
    #     tp_percent=0.07,  # +7% от цены входа
    #     side="buy"
    # )
    # print("Тейк профит по прибыли установелн:", result_take_profit)
    # result_partial_output_take_profit = position_manager.set_take_profit(
    #     symbol="BTCUSDT",
    #     entry_price=42000,
    #     quantity=0.001,
    #     partial_targets=[
    #         {"percent": 0.5, "target": 43000},
    #         {"percent": 0.3, "target": 44000},
    #         {"percent": 0.2, "target": 45500},
    #     ],
    #     side="buy"
    # )
    # print("Частичный выход установлен:", result_partial_output_take_profit)
    # try:
    # ...
    # except ValueError as e:
    # ...

if __name__ == "__main__":
    main()