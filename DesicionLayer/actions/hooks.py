"""全局钩子占位点。

当前项目还未实现统一事件总线，这些函数用于约定可扩展生命周期。
"""


def ON_ACTION_RESOLVE():
    """动作结算后触发。"""
    pass


def ON_LOOT_ROLL():
    """战利品抽取时触发。"""
    pass


def ON_PRICE_QUERY():
    """查询价格时触发。"""


def ON_DAILY_SETTLE(*_args, **_kwargs):
    """每日结算时触发。"""
    pass


def ON_ENTER_LOCATION():
    """进入地点时触发。"""
    pass


def ON_DIALOGUE_END():
    """对话结束时触发。"""
    pass


def ON_ATTRIBUTE_UPDATE():
    """属性更新时触发。"""
    pass


def ON_END_OF_ROUND():
    """单个 agent 结束回合时触发。"""
    pass
