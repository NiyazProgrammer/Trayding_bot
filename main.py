from api.exchange_factory import ExchangeFactory
from trayding.risk_manager import RiskManager
from trayding.position_manager import PositionManager

def main():
    exchange = ExchangeFactory.create_connector("bitget")
    risk_manager = RiskManager(exchange)
    position_manager = PositionManager(exchange, risk_manager)

    try:
        position_manager.open_position(
            symbol="BTCUSDT",
            side="buy",           
            amount_type="fixed",
            market_type="futures",  
            leverage=10.0,        
            amount=100,       
            product_type="USDT-FUTURES",
            margin_coin="USDT"
        )
    except ValueError as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()