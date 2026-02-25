"""角色记忆容器（当前以行动记录为主）。"""

from dataclasses import dataclass,field
from typing import List,Dict,Any

@dataclass
class MemoryStore:
    act_records: List[List[Dict[str,Any]]] = field(default_factory=list)
    
    def get_recent(self) -> List[List[Dict[str,Any]]]:
        # 当前只返回最近一天，可按需要扩展时间窗口。
        return self.act_records[-1:]
    
