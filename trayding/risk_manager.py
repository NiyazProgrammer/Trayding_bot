from abc import ABC
from utils.logging_setup import setup_logger
from config import ExchangeConfig

class RiskManager:
    def __init__(self, exchange_connector):
        self.exchange = exchange_connector
        self.logger = setup_logger()
        self.max_position_size = 0
        self.user_max_position_percentage = {}

    # Временный для проверки макс позиции
    def set_user_max_position(self, user_id: int, percentage: float):
        if percentage < ExchangeConfig.MIN_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MIN_USER_POSITION_PERCENTAGE
        elif percentage > ExchangeConfig.MAX_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MAX_USER_POSITION_PERCENTAGE
        
        self.user_max_position_percentage[user_id] = percentage
        self.logger.info(f"Пользователь {user_id} установил лимит: {percentage * 100}%")
    
    def check_balance(
        self,
        symbol: str,
        required_amount: float,
        market_type: str,  
        leverage: float = 1.0,
        product_type: str = None,
        margin_coin: str = None
    ) -> bool:
        available_balance = self.exchange.get_available_balance(symbol, market_type, product_type, margin_coin)
        # Тут вместо ExchangeConfig.MAX_POSITION_SIZE мы будем брать из свойства структуры юзера
        self.max_position_size = available_balance * ExchangeConfig.MAX_POSITION_SIZE

        if required_amount > self.max_position_size:
            self.logger.warning(
                f"Превышен лимит: {required_amount} > {self.max_position_size}"
            )
            return False
    
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        total_required = effective_amount + (effective_amount * ExchangeConfig.COMMISSION_RATE)

        self.exchange.logger.debug(
            f"Проверка баланса ({market_type}): "
            f"Доступно {available_balance} USDT, "
            f"Требуется {total_required} USDT (включая комиссию)"
        )

        return available_balance >= total_required
    
    def check_risk_limits(self, quantity: float) -> bool:
        if quantity > self.max_position_size:
            self.exchange.logger.error(
                f"Превышен максимальный размер позиции: {quantity} > {self.max_position_size}"
            )
            return False
        return True
    
    def validate_position(
        self, 
        symbol: str, 
        required_amount: float,
        quantity: float,
        market_type: str,
        leverage: float = 1.0,
        product_type: str = None,
        margin_coin: str = None
    ) -> bool:
        if not self.check_balance(symbol, required_amount, market_type, leverage, product_type):
            raise ValueError("Недостаточно средств для открытия позиции")
        if not self.check_risk_limits(quantity):
            raise ValueError("Превышен максимальный размер позиции")
        if quantity <= 0:
            raise ValueError("Объем позиции должен быть больше нуля")
        return True
    