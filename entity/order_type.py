from enum import Enum

class OrderType(Enum):
    PROFIT_PLAN = "profit_plan"
    LOSS_PLAN = "loss_plan"
    MOVING_PLAN = "moving_plan"
    MARKET = "market"
    LIMIT = "limit"