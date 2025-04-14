from api.base_exchange_connector import BaseExchangeConnector

class PositionManager:
    def __init__(self, exchange_connector: BaseExchangeConnector, risk_manager):
        self.exchange = exchange_connector
        self.risk_manager = risk_manager

    def open_position(
        self,
        symbol: str,
        side: str,
        amount_type: str,
        market_type: str = "spot",       
        amount: float = None,
        percentage: float = None,
        **kwargs
    ):
        if amount_type not in ("fixed", "percentage"):
            raise ValueError("Неподдерживаемый тип объёма")
        
        available_balance = self.exchange.get_available_balance(
            symbol,
            account_type=market_type,
            **kwargs
        )
        
        if amount_type == "fixed":
            required_amount = amount
        else:
            required_amount = available_balance * percentage
        
        quantity = self.exchange.calculate_quantity(
            required_amount=required_amount,
            symbol=symbol,
            market_type=market_type,
            **kwargs
        )
        
        self.risk_manager.validate_position(
            symbol=symbol,
            required_amount=required_amount,
            quantity=quantity,
            market_type=market_type,
            **kwargs
        )

        order_params = self.exchange.create_order_params(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="market",
            **kwargs
        )
        return self.exchange.place_order(order_params, market_type, **kwargs)