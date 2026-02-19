from View.trading_session import TradingSession

class TradingController:
    def __init__(self, trading_service_factory):
        self._factory = trading_service_factory
        self._session = None

    def attach_signal_handler(self, on_signal):
        if not self._session:
            raise RuntimeError("Trading session not created")
        self._session.set_signal_handler(on_signal)

    def start(self, params, on_signal):
        # If there's an existing session that's running, raise error
        if self._session and self._session.is_running:
            raise RuntimeError("Trading already running")

        # If there's an existing stopped session, clean it up
        if self._session and not self._session.is_running:
            self._session = None

        trading_service = self._factory(params)

        timeframe = trading_service.timeframe
        if trading_service.timeframe.endswith("m"):
            interval_sec = 30
        else:
            interval_sec = 60

        self._session = TradingSession(
            trading_service=trading_service,
            interval_sec=interval_sec,
            on_signal=on_signal
        )
        self._session.start()
        
        return trading_service

    def stop(self):
        if not self._session or not self._session.is_running:
            raise RuntimeError("Trading is not running")

        self._session.stop()

    def is_running(self) -> bool:
        return self._session is not None and self._session.is_running