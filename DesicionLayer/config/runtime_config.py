"""AgentRuntime 的运行参数。"""


class AgentRuntimeConfig:
    # 生存指标低阈值（可用于未来强制策略触发）。
    hunger_low: float = 15.0
    thirst_low: float = 15.0
    fatigue_low: float = 20.0

    # act 阶段最大重试次数。
    max_action_retries: int = 2

    # 记忆窗口长度（当前尚未完全接入裁剪逻辑）。
    max_working_events: int = 12
    max_recalled_events: int = 5

    # 至少间隔多少 step 后再次触发反思/计划。
    reflect_min_interval_steps = 20
    plan_min_interval_steps = 20
