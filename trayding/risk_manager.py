from utils.logging_setup import setup_logger
from config import ExchangeConfig
from api.base_exchange_connector import BaseExchangeConnector
from datetime import datetime, timezone

class RiskManager:
    def __init__(self, exchange_connector: BaseExchangeConnector, daily_loss_limit: float):
        self.exchange = exchange_connector
        self.logger = setup_logger()
        self.max_position_size = 0
        self.user_max_position_percentage = {}
        self.daily_loss_limit = daily_loss_limit

    # Временный для проверки макс позиции
    def set_user_max_position(self, user_id: int, percentage: float):
        if percentage < ExchangeConfig.MIN_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MIN_USER_POSITION_PERCENTAGE
        elif percentage > ExchangeConfig.MAX_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MAX_USER_POSITION_PERCENTAGE
        
        self.user_max_position_percentage[user_id] = percentage
        self.logger.info(f"Пользователь {user_id} установил лимит: {percentage * 100}%")

    def get_today_timestamp_range(self):
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return int(start.timestamp() * 1000), int(now.timestamp() * 1000)

    def check_balance(
        self,
        symbol: str,
        required_amount: float,
        market_type: str,
        product_type: str = None,
        margin_coin: str = None,
        leverage: float = None,
        order_type: str = "market"
   ) -> bool:
        available_balance = self.exchange.get_available_balance(
            symbol,
            account_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin,
        )
        # Тут вместо ExchangeConfig.MAX_POSITION_SIZE мы будем брать из свойства структуры юзера
        self.max_position_size = available_balance * ExchangeConfig.MAX_POSITION_SIZE

        if required_amount > self.max_position_size:
            self.logger.warning(
                f"Превышен лимит: {required_amount} USDT > {self.max_position_size} USDT"
            )
            return False
        
        leverage = leverage
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        commission_rate = self.exchange.get_commission_rate(market_type, order_type)
        total_required = effective_amount + (effective_amount * commission_rate)

        self.logger.debug(f"Проверка баланса ({market_type}): ")

        return available_balance >= total_required

    def validate_position(
        self,
        symbol: str,
        required_amount: float,
        quantity: float,
        market_type: str,
        product_type: str = None,
        margin_coin: str = None,
        leverage: float = None,
        order_type: str = "market"
    ) -> bool:
        if not self.check_balance(
                symbol,
                required_amount,
                market_type,
                product_type,
                margin_coin,
                leverage,
                order_type
        ):
            print("Недостаточно средств для открытия позиции")
            return False
        if quantity <= 0:
            print("Объем позиции должен быть больше нуля")
            return False
        return True

    def is_trading_allowed(self, product_type="SUSDT-FUTURES") -> bool:
        """
        Проверяет, разрешена ли торговля на основе дневного PnL.
        Если убытки за день превысили лимит, торговля блокируется.
        """
        start_ts, end_ts = self.get_today_timestamp_range()

        try:
            daily_pnl = 0.0

            for business_type in ["close_long", "close_short"]:
                bills_response = self.exchange.get_account_bills(
                    product_type=product_type,
                    start_time=start_ts,
                    end_time=end_ts,
                    business_type=business_type,
                    limit=100
                )

                if not bills_response:
                    continue

                bills_data = bills_response.json()
                bills = bills_data.get("data", {}).get("bills", [])
                pnl = sum(float(bill["amount"]) for bill in bills)
                daily_pnl += pnl

            print(f"[RiskManager] Daily PnL: {daily_pnl:.2f} USDT")

            return daily_pnl >= -abs(self.daily_loss_limit)

        except Exception as e:
            raise ValueError(f"[RiskManager] Ошибка при проверке дневного PnL: {e}")

