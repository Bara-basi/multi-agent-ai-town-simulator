"""角色静态定义。"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union

ActorId = str 

@dataclass(frozen=True, slots=True)
class ActorDef:
    id: ActorId
    name: str
    age:int
    gender: str
    description: str = ""
    skill: Optional[Union[str, Callable[..., Any],Dict[str,Any]]] = None
    info: Optional[str] = None
    

    def snapshot(self) -> Dict[str, Any]:
        # skill 仅在是字符串时透出，避免把可调用对象塞进 prompt。
        return {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "description": self.description,
            "info": self.info or "",
            "skill": self.skill if isinstance(self.skill, str) else "",
        }
