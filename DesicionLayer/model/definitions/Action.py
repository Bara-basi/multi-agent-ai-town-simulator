from __future__ import annotations
"""动作数据结构（可作为 LLM 输出的中间表示）。"""
from dataclasses import dataclass
from typing import Optional,Dict,Any

@dataclass
class Action:
    # name 为动作名，params 为动作参数。
    name:str 
    params:Dict[str,Any]
    
