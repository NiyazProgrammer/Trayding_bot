import time
import uuid
import config
from api.exchange_factory import ExchangeFactory
from trayding.risk_manager import RiskManager
from trayding.position_manager import PositionManager
from config import TelegramConfig
from config import ExchangeConfig
from api.bitget_connector import BitgetConnector
from datetime import datetime, timezone

def main():
    exchange = ExchangeFactory.create_connector("bitget", True)
    risk_manager = RiskManager(exchange,daily_loss_limit=ExchangeConfig.DAILY_LOSS_LIMIT)
    position_manager = PositionManager(exchange, risk_manager)

    # Проверка открытия позиции на споте
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
    #     side="buy",
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

    # Проставления трейлинг стопа
    # result_trayling_stop = position_manager.set_trailing_stop(
    #     symbol="BTCUSDT",
    #     quantity=0.01,
    #     side="buy",
    #     trailing_distance=0.03,  # 3%
    #     activation_price=105000,  # сработает, когда цена достигнет 43k (необязательно)
    #     product_type="USDT-FUTURES",
    #     margin_coin="USDT"
    # )
    # print("Частичный выход установлен:", result_trayling_stop)

    # Проставление лимитного ордера
    # result_pending_order = position_manager.set_pending_order(
    #     symbol="BTCUSDT",
    #     quantity=0.01,
    #     side="buy",
    #     trigger_price=50000,  # когда цена <= 50000
    #     price=49900,  # выставим лимитку по 49900
    #     order_type="limit",
    # )
    # print("Лимитный отложенный ордер установлен:", result_pending_order)

    # Проставление стоп-маркет ордера
    # result_pending_order = position_manager.set_pending_order(
    #     symbol="BTCUSDT",
    #     quantity=0.01,
    #     side="sell",
    #     trigger_price=42000,  # когда цена <= 42000
    #     order_type="market",
    #     plan_type="normal_plan"
    # )
    # print("Стоп-маркет ордер установлен:", result_pending_order)

    
    # Отмена конкретных ордеров по ID
    # result_cancel_trigger_order = exchange.cancel_trigger_order(
    #     product_type="USDT-FUTURES",
    #     symbol="BTCUSDT",
    #     margin_coin="USDT",
    #     order_id_list=[
    #         {"orderId": "1321389568909918208", "clientOid": ""},
    #     ]
    # )
    # print("Конкретные плановые ордера отменены:", result_cancel_trigger_order)

    # Отмена всех ордеров по символу и типу продукта
    # result_cancel_all = exchange.cancel_trigger_order(
    #     product_type="USDT-FUTURES",
    #     symbol="BTCUSDT",
    #     margin_coin="USDT"
    # )
    # print("Все ордера по BTCUSDT отменены:", result_cancel_all)
    
    # Отмена ордеров определенного типа
    # result_cancel_by_type = exchange.cancel_trigger_order(
    #     product_type="USDT-FUTURES",
    #     symbol="BTCUSDT",
    #     margin_coin="USDT",
    #     plan_type="normal_plan"  # или profit_plan, loss_plan, moving_plan
    # )
    # print("Ордера типа normal_plan отменены:", result_cancel_by_type)


    # СОЗДАНИЕ ОРДЕРОВ ДЛЯ ПОСЛЕДУЮЩЕГО ИЗМЕНЕНИЯ:
    
    # 1.1. Создание обычного отложенного ордера (normal_plan)
    # result_create_normal = position_manager.set_pending_order(
    #     symbol="BTCUSDT",
    #     quantity=0.01,
    #     side="buy",
    #     trigger_price=93000,  # когда цена достигнет 93000
    #     price=92500,  # исполнить лимитный ордер по 92500
    #     order_type="limit",
    #     market_type="futures",
    #     product_type="USDT-FUTURES",
    #     margin_coin="USDT",
    #     margin_mode="isolated"
    # )
    # print("Обычный отложенный ордер создан:", result_create_normal)
    # order_id_normal = result_create_normal.get('data', {}).get('orderId') if result_create_normal else None

    # 1.2. Изменение обычного отложенного ордера (normal_plan)
    # result_modify_order = exchange.modify_trigger_order(
    #     symbol="BTCUSDT",
    #     product_type="USDT-FUTURES",
    #     plan_type="normal_plan",
    #     order_id=order_id_normal,  # используем ID созданного ордера
    #     new_size="0.02",  # новый размер
    #     new_price="95000",  # новая цена исполнения (для лимитных)
    #     new_trigger_price="94000",  # новая цена активации
    #     new_trigger_type="mark_price"  # новый тип триггера
    # )
    # print("Обычный ордер изменен:", result_modify_order)
    
    # 2.1. Создание трейлинг-стопа (track_plan)
    # result_create_trailing = position_manager.set_trailing_stop(
    #     symbol="BTCUSDT",
    #     quantity=0.01,
    #     side="buy",  # направление позиции
    #     trailing_distance=3.0,  # 3% трейлинг
    #     activation_price=98000,  # активация при достижении 98000
    #     market_type="futures",
    #     product_type="USDT-FUTURES",
    #     margin_coin="USDT",
    #     margin_mode="isolated"
    # )
    # print("Трейлинг-стоп создан:", result_create_trailing)
    # trailing_order_id = result_create_trailing.get('data', {}).get('orderId') if result_create_trailing else None

    # 2.2. Изменение трейлинг-стопа (track_plan)
    # result_modify_trailing = exchange.modify_trigger_order(
    #     symbol="BTCUSDT",
    #     product_type="USDT-FUTURES",
    #     plan_type="track_plan",
    #     order_id=trailing_order_id,  # используем ID созданного трейлинг-стопа
    #     new_callback_ratio="5.0",  # изменить расстояние трейлинга на 5%
    #     new_trigger_price="100000"  # новая цена активации (необязательно)
    # )
    # print("Трейлинг-стоп изменен:", result_modify_trailing)

    # try:
    # ...
    # except ValueError as e:
    # ...


if __name__ == "__main__":
    main()
