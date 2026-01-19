from strategies.entity.strategy_state import StrategyState, AveragingLevel
from strategies.wavexTradingService import WAVEXTradingService
from strategies.indicatorService import IndicatorService
from strategies.bitgetCandleService import BitgetCandleService
from trayding.position_manager import PositionManager
from api.exchange_factory import ExchangeFactory
from trayding.risk_manager import RiskManager
from config import ExchangeConfig

import time
import logging


logging.basicConfig(level=logging.INFO)

def create_initial_state() -> StrategyState:
    """
    Инициализация state из конфига
    """
    config = ExchangeConfig.STRATEGY_CONFIG

    state = StrategyState()

    for item in config["averaging"]:
        state.averaging_levels.append(
            AveragingLevel(
                percentage=item["percent"],
                enabled=item["enabled"]
            )
        )

    return state

def main():

    SYMBOL = "BTCUSDT"
    TIMEFRAME = "1H"

    # --- Candle service ---
    candle_service = BitgetCandleService()

    # --- Indicator service ---
    indicator_service = IndicatorService(candle_service)

    # --- Exchange + Position Manager ---
    exchange = ExchangeFactory.create_connector("bitget", True)

    risk_manager = RiskManager(
        exchange,
        daily_loss_limit=ExchangeConfig.DAILY_LOSS_LIMIT
    )

    position_manager = PositionManager(exchange, risk_manager)

    # --- Strategy state ---
    state = create_initial_state()

    # --- Trading Service ---
    trading_service = WAVEXTradingService(
        user_id="user1",
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        position_manager=position_manager,
        state_strategy=state,
        candle_service=candle_service,
        indicator_service=indicator_service
    )

    logging.info("Starting WAVEX bot...")

    # --- Main loop ---
    while True:

        trading_service.process_signal()

        # Проверяем раз в минуту
        time.sleep(60)


if __name__ == "__main__":
    main()