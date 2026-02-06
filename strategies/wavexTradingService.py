from typing import Optional
from strategies.entity.strategy_state import StrategyState
from strategies.CandleServiceProtocol import CandleService
from strategies.indicatorService import IndicatorService
from strategies.wawexstrategy  import WAVEXStrategy
from trayding.PositionManagerProtocol import PositionManagerProtocol
from utils.logging_setup import setup_logger

logger = setup_logger()



class WAVEXTradingService:

    def __init__(
        self,
        user_id: str,
        symbol: str,
        timeframe: str = "1H",
        amount: float = 1.0,
        leverage: float = 1.0,
        position_manager: PositionManagerProtocol = None,
        state_strategy: StrategyState = None,
        candle_service: CandleService = None,
        indicator_service: IndicatorService = None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.amount = amount
        self.leverage = leverage

        # --- Services ---
        self.pm = position_manager
        self.state = state_strategy
        self.candle_service = candle_service # BitgetCandleService()
        self.indicator_service = indicator_service # IndicatorService(self.candle_service)

        # --- Strategy ---
        self.strategy = WAVEXStrategy()

    def process_signal(self):

        try:
            # 1. Получаем индикаторы
            data = self.indicator_service.get_indicators(
                symbol=self.symbol,
                timeframe=self.timeframe
            )

            if data is None:
                logger.info("No new candle was found")
                return

            price = data["price"]
            ema = data["ema"]
            rsi = data["rsi"]

            logger.info(f"Price: {price}, EMA: {ema}, RSI: {rsi}")

            # 2. Вызываем стратегию
            signal = self.strategy.on_candle_close(
                price=price,
                rsi=rsi,
                ema=ema,
                state=self.state
            )

            self.handler_signal(signal, price)

            return signal

        except Exception as e:
            logger.error(f"Error in bot cycle: {e}")


    def handler_signal(
        self,
        signal: Optional[dict],
        price: float
    ):
        if not signal:
            logger.info("No signal")
            return

        signal_type = signal["signal"]
        logger.info(f"Signal received: {signal_type}")

        try:

            # ----- BUYX -----
            if signal_type == "BUYX":

                self.pm.open_position(
                    symbol=self.symbol,
                    side="buy",
                    amount_type="fixed",
                    amount=self.amount,
                    order_type="market",
                    market_type="futures",
                    leverage=self.leverage,
                    product_type="USDT-FUTURES",
                    margin_coin="USDT",
                    position_action="open",
                    margin_mode="crossed"
                )

                self.state.position_open = True
                self.state.entry_price = price

                for lvl in self.state.averaging_levels:
                    lvl.level = price * (1 - lvl.percentage / 100)
                    lvl.filled = False

                logger.info("Executed BUYX")

            # ----- AVERAGING -----
            elif signal_type.startswith("AVER"):

                index = signal["index"]

                self.pm.open_position(
                    symbol=self.symbol,
                    side="buy",
                    amount_type="fixed",
                    amount=self.amount,
                    order_type="market",
                    market_type="futures",
                    leverage=self.leverage,
                    product_type="USDT-FUTURES",
                    margin_coin="USDT",
                    position_action="open",
                    margin_mode="crossed"
                )

                self.state.averaging_levels[index].filled = True

                logger.info(f"Executed {signal_type}")

            # ----- CLOSEX -----
            elif signal_type == "CLOSEX":

                self.pm.close_position_full(
                    symbol=self.symbol,
                    product_type="USDT-FUTURES",
                    margin_coin="USDT",
                    order_type="market"
                )

                self.state.position_open = False
                self.state.entry_price = None

                for lvl in self.state.averaging_levels:
                    lvl.level = None
                    lvl.filled = False

                logger.info("Executed CLOSEX")

        except Exception as e:
            logger.error(f"Error in bot cycle: {e}")