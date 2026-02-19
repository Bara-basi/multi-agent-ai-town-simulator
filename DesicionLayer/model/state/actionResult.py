from __future__ import annotations

from typing import Any, Dict, Optional


class ActionResult:
 
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
        return self.status

    @property
    def message(self) -> str:
        return self.msg


    @property
    def finish(self) -> bool:
        return self._finish
