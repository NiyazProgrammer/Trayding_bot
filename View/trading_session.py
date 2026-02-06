import threading
import time
from utils.logging_setup import setup_logger

logger = setup_logger()

class TradingSession:
    def __init__(self, trading_service, interval_sec: int, on_signal):
        self._trading_service = trading_service
        self._interval = interval_sec
        self._on_signal = on_signal

        self._running = False
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_signal_handler(self, on_signal):
        self._on_signal = on_signal

    def start(self) -> None:
        if self._running:
            raise RuntimeError("Trading session already running")

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True
        )
        self._thread.start()

        logger.info("Trading session started")

    def stop(self) -> None:
        self._running = False

        if self._thread:
            self._thread.join(timeout=2)

        logger.info("Trading session stopped")

    def _run_loop(self):
        while self._running:
            try:
                signal = self._trading_service.process_signal()

                if signal and self._on_signal:
                    if signal and callable(self._on_signal):
                        self._on_signal(signal)

            except Exception as e:
                logger.exception("Trading loop error")
                # Don't let exceptions crash the thread
                # Continue with the next iteration
                pass

            # Only sleep if still running
            if self._running:
                time.sleep(self._interval)

