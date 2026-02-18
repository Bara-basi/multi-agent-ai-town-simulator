from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from model.state.actionResult import ActionResult

ActionValidator = Callable[["ActionContext", Any], Optional[ActionResult]]
ActionHandler = Callable[["ActionContext", Any], ActionResult]


@dataclass
class ActionContext:
    world: Any
    dispatch: Any
    config: Any
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
    def deco(fn: ActionHandler) -> ActionHandler:  # 定义一个装饰器函数deco，接受一个ActionHandler类型的参数fn，并返回一个ActionHandler类型的函数
        if action_name in _REGISTRY:  # 检查action_name是否已经在注册表中
            raise ValueError(f"Action {action_name} already registered")
        _REGISTRY[action_name] = Entry(handler=fn, validators=validators or [])
        for alias in aliases or []:
            _ALIASES[alias] = action_name
        return fn

    return deco


def resolve_name(name: str) -> str:
    return _ALIASES.get(name, name)


def get_entry(name: str) -> Entry:
    name = resolve_name(name)
    if name not in _REGISTRY:
        raise ValueError(f"Action {name} is not registered")
    return _REGISTRY[name]

