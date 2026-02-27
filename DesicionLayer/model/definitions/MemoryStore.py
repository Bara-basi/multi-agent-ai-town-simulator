"""角色记忆容器（当前以行动记录为主）。"""

from dataclasses import dataclass,field
from typing import List,Dict,Any

@dataclass
class MemoryStore:
    act_records: List[List[str]] = field(default_factory=lambda: [[]])
    
    def get_recent(self) -> List[str]:
        # 当前只返回最近一天，可按需要扩展时间窗口。
        return self.act_records[-1]
    def observe(self):
        return "\n".join(self.get_recent())