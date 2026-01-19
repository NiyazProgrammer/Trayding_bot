from typing import Dict, List, Optional
import logging
from config import ExchangeConfig
from strategies.entity.strategy_state import StrategyState

class WAVEXStrategy:
    def __init__(self, user_id: Optional[str] = None):
        self.logger = logging.getLogger("WAVEXStrategy")
        self.user_id = user_id

        config = ExchangeConfig.STRATEGY_CONFIG

        # Strategy parameters
        self.RSI_STOP = config["rsi_stop"]
        self.ANTI_RSI_STOP = config["anti_rsi_stop"]

        self.logger.info("WAVEX Strategy initialized")

    def on_candle_close(
            self,
            price: float,
            rsi: float,
            ema: float,
            state: StrategyState
    ) -> Optional[Dict]:
        try:
            self.logger.debug(f"Price: {price}, EMA: {ema}, RSI: {rsi}")

            # Entry logic (BUYX) - only if no position is open
            if not state.position_open:
                if price < ema and rsi < self.RSI_STOP:
                    self.logger.info("Signal: BUYX")

                    return {
                        "signal": "BUYX",
                        "price": price
                    }

            # Averaging logic - only if position is open
            if state.position_open and state.entry_price is not None:
                for id, avg_level in enumerate(state.averaging_levels):
                    if (
                            avg_level.enabled
                            and not avg_level.filled
                            and avg_level.level is not None
                            and price <= avg_level.level
                    ):

                        self.logger.info(f"Signal: AVER{id + 1}")
                        return {
                            "signal": f"AVER{id + 1}",
                            "index": id,
                            "price": price
                        }

            # Exit logic (CLOSEX) - only if position is open
            if state.position_open:
                if price > ema and rsi > self.ANTI_RSI_STOP:
                    self.logger.info("Signal: CLOSEX")

                    return {
                        "signal": "CLOSEX",
                        "price": price
                    }

            # No signal
            return None


        except Exception as e:
            self.logger.error(f"Error in WAVEX strategy: {e}")
            return {"signal": None, "error": str(e)}

 