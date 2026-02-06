def create_wavex_trading_service(params):
    from strategies.entity.strategy_state import StrategyState, AveragingLevel
    from strategies.wavexTradingService import WAVEXTradingService
    from strategies.indicatorService import IndicatorService
    from strategies.bitgetCandleService import BitgetCandleService
    from trayding.position_manager import PositionManager
    from api.exchange_factory import ExchangeFactory
    from trayding.risk_manager import RiskManager
    from config import ExchangeConfig

    exchange = ExchangeFactory.create_connector("bitget", True)

    risk_manager = RiskManager(
        exchange,
        daily_loss_limit=ExchangeConfig.DAILY_LOSS_LIMIT
    )

    position_manager = PositionManager(exchange, risk_manager)

    candle_service = BitgetCandleService(exchange)
    indicator_service = IndicatorService(candle_service)

    state = StrategyState()
    for item in ExchangeConfig.STRATEGY_CONFIG["averaging"]:
        state.averaging_levels.append(
            AveragingLevel(
                percentage=item["percent"],
                enabled=item["enabled"]
            )
        )

    leverage = resolve_leverage(
        timeframe=params.timeframe,
        user_leverage=params.leverage
    )

    return WAVEXTradingService(
        user_id="user1",
        symbol=params.symbol,
        timeframe=params.timeframe,
        amount=params.amount,
        leverage=leverage,
        position_manager=position_manager,
        state_strategy=state,
        candle_service=candle_service,
        indicator_service=indicator_service
    )

def resolve_leverage(timeframe: str, user_leverage: float | None = None) -> float:
    from config import ExchangeConfig

    # Если пользователь указал плечо — используем его
    if user_leverage and user_leverage >= 1:
        return user_leverage

    tf = timeframe.lower()
    leverage = ExchangeConfig.DEFAULT_LEVERAGE_BY_TIMEFRAME.get(tf)

    if leverage:
        return leverage

    return ExchangeConfig.FALLBACK_LEVERAGE