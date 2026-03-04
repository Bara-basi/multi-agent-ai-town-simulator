from __future__ import annotations

"""Action execution entry: normalize, validate, and dispatch handlers."""

import inspect
from typing import Any, Dict

import actions.handlers  # ensure built-in handlers are registered
from actions.action_registry import ActionContext, get_entry
from model.state.actionResult import ActionResult


class _ActionView:
    """Unified action view compatible with dict/object inputs."""

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
        if isinstance(name, str) and name.startswith("skill-"):
            payload.setdefault("skill_name", name[len("skill-") :])
            name = "skill"
        payload["name"] = name
        return _ActionView(payload)

    async def execute(self, action: Any, *args, **kwargs) -> ActionResult:
        act = self._normalize_action(action, **kwargs)
        name = act.get("name")
        if not name:
            return ActionResult(status=False, code="INVALID", message="action name is required")

        try:
            entry = get_entry(name)
        except Exception:
            return ActionResult(status=False, code="INVALID_ACTION", message=f"unknown action: {name}")

        for validator in entry.validators:
            maybe = validator(self.ctx, act)
            if inspect.isawaitable(maybe):
                maybe = await maybe
            if maybe is not None:
                return maybe

        try:
            out = entry.handler(self.ctx, act)
            if inspect.isawaitable(out):
                out = await out
            return out
        except KeyError as e:
            return ActionResult(status=False, code="NOT_FOUND", message=str(e))
        except Exception as e:
            if self.ctx.logger:
                self.ctx.logger.exception("Action execution failed")
            return ActionResult(status=False, code="CRASH", message=f"action execution error: {e}")

