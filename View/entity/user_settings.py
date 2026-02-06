from dataclasses import dataclass

@dataclass
class UserSettings:
    symbol: str = "BTCUSDT"
    timeframe: str = "1H"
    amount: float = 100
    leverage: int | None = None