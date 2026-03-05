from __future__ import annotations

"""动作注册中心：管理 handler、validator 和动作别名。"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from model.state.actionResult import ActionResult

ActionValidator = Callable[["ActionContext", Any], Optional[ActionResult]]
ActionHandler = Callable[["ActionContext", Any], ActionResult]


@dataclass
class ActionContext:
    # 运行时上下文：把执行动作所需对象集中传给 handler/validator。
    world: Any
    dispatch: Any
    catalog: Any
    logger: Any


@dataclass
class Entry:
    handler: ActionHandler
    validators: List[ActionValidator] = field(default_factory=list)


_REGISTRY: Dict[str, Entry] = {}
_ALIASES: Dict[str, str] = {}


def register(
    action_name: str,
    *,
    aliases: Optional[List[str]] = None,
    validators: Optional[List[ActionValidator]] = None,
):
    """注册动作处理函数。"""

    def deco(fn: ActionHandler) -> ActionHandler:
        if action_name in _REGISTRY:
            raise ValueError(f"动作 `{action_name}` 已被注册")
        _REGISTRY[action_name] = Entry(handler=fn, validators=validators or [])
        for alias in aliases or []:
            _ALIASES[alias] = action_name
        return fn

    return deco


def resolve_name(name: str) -> str:
    # 将别名归一到主动作名。
    return _ALIASES.get(name, name)


def get_entry(name: str) -> Entry:
    name = resolve_name(name)
    if name not in _REGISTRY:
        raise ValueError(f"动作 `{name}` 未注册")
    return _REGISTRY[name]
