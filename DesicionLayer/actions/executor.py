from __future__ import annotations

"""动作执行总入口：动作标准化、注册查询、校验和 handler 调用。"""

from typing import Any, Dict

from actions.action_registry import ActionContext, get_entry
from model.state.actionResult import ActionResult


class _ActionView:
    """统一的动作读取视图，兼容 dict / object 输入。"""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def __getattr__(self, name: str) -> Any:
        if name in self._payload:
            return self._payload[name]
        raise AttributeError(name)

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._payload.get(key, default)


class ActionExecutor:
    def __init__(self, world, dispatch, config, catalog, logger):
        self.ctx = ActionContext(world, dispatch, config, catalog, logger)

    def _normalize_action(self, action: Any, **kwargs) -> _ActionView:
        # 1) 合并动作主体 2) 合并外部补充参数（如 actor_id）。
        payload: Dict[str, Any] = {}
        if isinstance(action, dict):
            payload.update(action)
        else:
            params = getattr(action, "params", None)
            if isinstance(params, dict):
                payload.update(params)
            if hasattr(action, "__dict__"):
                payload.update(vars(action))

        for k, v in kwargs.items():
            payload.setdefault(k, v)

        name = payload.get("name") or payload.get("type")
        # 历史兼容：skill-xxx 归一成 skill + skill_name。
        if isinstance(name, str) and name.startswith("skill-"):
            payload.setdefault("skill_name", name[len("skill-") :])
            name = "skill"
        payload["name"] = name
        return _ActionView(payload)

    def execute(self, action: Any, *args, **kwargs) -> ActionResult:
        act = self._normalize_action(action, **kwargs)
        name = act.get("name")
        if not name:
            return ActionResult(status=False, code="INVALID", message="动作名称未指定")

        try:
            entry = get_entry(name)
        except Exception:
            return ActionResult(status=False, code="INVALID_ACTION", message=f"未知动作: {name}")

        for validator in entry.validators:
            maybe = validator(self.ctx, act)
            if maybe is not None:
                return maybe

        try:
            return entry.handler(self.ctx, act)
        except KeyError as e:
            return ActionResult(status=False, code="NOT_FOUND", message=str(e))
        except Exception as e:
            if self.ctx.logger:
                self.ctx.logger.exception("Action execution failed")
            return ActionResult(status=False, code="CRASH", message=f"执行动作时发生错误: {e}")
