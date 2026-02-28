"""AgentRuntime 的运行参数。"""


class AgentRuntimeConfig:
    # 生存指标低阈值（可用于未来强制策略触发）。
    hunger_low: float = 15.0
    thirst_low: float = 15.0
    fatigue_low: float = 20.0

    # act 阶段最大重试次数。
    max_action_retries: int = 2
    # 执行失败后，允许在同一 tick 内基于错误反馈重试动作。
    max_replan_after_action_error: int = 2
    # 连续重复相同动作达到阈值后触发循环保护（例如阈值=2，第三次会被拦截）。
    repeat_action_guard_threshold: int = 2
    # 同一物品连续同向交易阈值（buy/buy/... 或 sell/sell/...）。
    repeat_trade_same_item_threshold: int = 3
    # 是否允许同一回合内对同一物品先买后卖或先卖后买（通常应关闭，防止交易震荡）。
    allow_opposite_trade_same_item_same_day: bool = False

    # 记忆窗口长度（当前尚未完全接入裁剪逻辑）。
    max_working_events: int = 12
    max_recalled_events: int = 5

    # 至少间隔多少 step 后再次触发反思/计划。
    reflect_min_interval_steps = 20
    plan_min_interval_steps = 20
