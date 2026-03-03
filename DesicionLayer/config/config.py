"""全局常量配置。"""

DEFAULT_MARKET_STOCK = 40
DEFAULT_MARKET_STOCK_INCREASE = 10
ACT_MODEL_NAME = "gpt-4.1-mini-2025-04-14"
PLAN_MODEL_NAME = "gpt-5-mini-2025-08-07"
REFLECT_MODEL_NAME = "gpt-5-mini-2025-08-07"

HUNGER_DECAY_PER_DAY = 8
THIRST_DECAY_PER_DAY = 10
FATIGUE_DECAY_PER_DAY = -20
FATIGUE_DECAY_PER_ACTION = 5

ATTR_CN_MAP = {"hunger":"饱食度","thirst":"水分值","fatigue":"精神值"}

KAPPA = {"comsumable": 0.11,
         "valuable": 0.11}

SIGMA = {"comsumable":0.15,
         "valuable":0.2}

RANDOM_EVENT_PORB = 0.1
