from utils.error_handling import retry_on_failure
from config import ExchangeConfig

class PositionManager:
    def __init__(self, exchange_connector, risk_manager):
        self.exchange = exchange_connector
        self.risk_manager = risk_manager

    @retry_on_failure(max_retries=3)
    def open_position(
        self,
        symbol: str,
        side: str,
        amount_type: str,
        market_type: str = "spot",  
        leverage: float = 1.0,     
        amount: float = None,
        percentage: float = None,
        product_type="USDT-FUTURES",
        margin_coin="USDT"
    ):
        if amount_type not in ("fixed", "percentage"):
            raise ValueError("Неподдерживаемый тип объёма")
        
        available_balance = self.exchange.get_available_balance(
            symbol,
            account_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin
        )
        
        if amount_type == "fixed":
            required_amount = amount
        else:
            required_amount = available_balance * percentage
        
        quantity = self.calculate_quantity(
            required_amount=required_amount,
            symbol=symbol,
            market_type=market_type,
            leverage=leverage,
            product_type=product_type
        )
        
        self.risk_manager.validate_position(symbol, required_amount, quantity, market_type, leverage, product_type, margin_coin)

        order_params = {
            "symbol": symbol,
            "side": side,
            "orderType": "market",
            "quantity": quantity
        }
        # return self.exchange.place_order(order_params)
        return 0
    
    def calculate_quantity(
        self,
        required_amount: float,
        symbol: str,
        market_type: str,
        leverage: float = 1.0,
        product_type: str = None,  
    ) -> float:
        
        ticker_data = self.exchange.fetch_ticker(symbol, market_type, product_type)['data'][0]
        current_price = float(ticker_data['lastPr'])
        
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        commission = 1 - ExchangeConfig.COMMISSION_RATE

        quantity = (effective_amount * commission) / current_price
        return round(quantity, ExchangeConfig.QUANTITY_PRECISION) 