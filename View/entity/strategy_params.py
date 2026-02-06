from dataclasses import dataclass

@dataclass
class StrategyParams:
    symbol: str
    timeframe: str
    amount: float
    leverage: int