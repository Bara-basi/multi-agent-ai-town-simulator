from __future__ import annotations

"""动作执行结果对象。兼容 status/success、msg/message 两套命名。"""

from typing import Any, Dict, Optional


class ActionResult:
    # 该类是执行层与 runtime/监控层之间的统一返回结构。
    def __init__(
        self,
        status: Optional[bool] = None,
        *,
        success: Optional[bool] = None,
        code: str = "OK",
        msg: str = "",
        message: Optional[str] = None,
        delta: Optional[Dict[str, Any]] = None,
        event: Optional[str] = None,
        finish: Optional[bool]=None,
    ) -> None:
        if status is None:
            status = bool(success) if success is not None else False
        self.status = bool(status)
        self.code = code
        self.msg = message if message is not None else msg
        self.delta = delta or {}
        self.event = event
        self._finish = bool(finish) if finish is not None else False

    @property
    def success(self) -> bool:
        # 与 status 同义，保留兼容旧调用。
        return self.status

    @property
    def message(self) -> str:
        # 与 msg 同义，便于上层统一读取。
        return self.msg


    @property
    def finish(self) -> bool:
        return self._finish
