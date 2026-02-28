"""角色记忆容器（当前以行动记录为主）。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class MemoryStore:
    # 每日记录：List[day_records], day_records: List[entry]
    # entry:
    # - {"kind":"plan_start","plan_id":int,"plan_text":str}
    # - {"kind":"action","plan_id":int,"message":str,"status":bool,"code":str,"finish":bool}
    act_records: List[List[Dict[str, Any]]] = field(default_factory=lambda: [[]])
    current_plan_id: int = 0

    def _today(self) -> List[Dict[str, Any]]:
        if not self.act_records:
            self.act_records.append([])
        return self.act_records[-1]

    def reset_today(self) -> None:
        if not self.act_records:
            self.act_records.append([])
        else:
            self.act_records[-1] = []
        self.current_plan_id = 0

    def start_plan(self, plan_id: int, plan_text: str = "") -> None:
        self.current_plan_id = int(plan_id or 0)
        self._today().append(
            {
                "kind": "plan_start",
                "plan_id": self.current_plan_id,
                "plan_text": str(plan_text or ""),
            }
        )

    def add_action(
        self,
        *,
        message: str,
        plan_id: Optional[int] = None,
        status: Optional[bool] = None,
        code: str = "",
        finish: Optional[bool] = None,
    ) -> None:
        pid = int(plan_id) if plan_id is not None else int(self.current_plan_id or 0)
        self._today().append(
            {
                "kind": "action",
                "plan_id": pid,
                "message": str(message or ""),
                "status": bool(status) if status is not None else None,
                "code": str(code or ""),
                "finish": bool(finish) if finish is not None else None,
            }
        )

    def get_recent(self, plan_id: Optional[int] = None) -> List[Dict[str, Any]]:
        records = self._today()
        if plan_id is None:
            return records
        return [r for r in records if int(r.get("plan_id", 0)) == int(plan_id)]

    @staticmethod
    def _render(entries: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for r in entries:
            kind = r.get("kind")
            if kind == "plan_start":
                lines.append(f"[计划#{r.get('plan_id', 0)}开始]")
            elif kind == "action":
                msg = str(r.get("message", "") or "").strip()
                if msg:
                    lines.append(msg)
        return "\n".join(lines)

    def observe_current_plan(self) -> str:
        pid = int(self.current_plan_id or 0)
        if pid <= 0:
            return ""
        return self._render(self.get_recent(plan_id=pid))

    def observe_previous_plans(self) -> str:
        pid = int(self.current_plan_id or 0)
        if pid <= 0:
            return ""
        prev = [r for r in self._today() if int(r.get("plan_id", 0)) < pid]
        return self._render(prev)

    def observe(self) -> str:
        return self._render(self.get_recent())
