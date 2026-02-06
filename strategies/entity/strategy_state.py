from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AveragingLevel:
    percentage: float # AVER_X
    level: Optional[float] = None # averx_level
    filled: bool = False # averx_filled
    enabled: bool = True # USE_AVER_X - в конфиг


@dataclass
class StrategyState:
    position_open: bool = False
    entry_price: Optional[float] = None
    averaging_levels: List[AveragingLevel] = field(default_factory=list)