from typing import Dict,List,Optional,Any
from model.definitions.Effect import Effect

"""效果管理器（预留系统）。当前仅提供增删查与简单计算骨架。"""

class EffectManager:
    effects:Dict[str,List[Effect]]
    
    def __init__(self):
        self.effects = {}

    def add_effect(self, effect:Effect):
        # 按 scope 分组存放效果，便于按上下文查询。
        self.effects.setdefault(effect.scope, []).append(effect)

    def remove_effect(self, effect:Effect):
        if effect.scope in self.effects and effect in self.effects[effect.scope]:
            self.effects[effect.scope].remove(effect)

    def extend_effects(self,scope:str,effects:List[Effect]):
        self.effects.setdefault(scope, []).extend(effects)

    def get_effects(self, scope:str) -> List[Effect]:
        return self.effects.get(scope,[])
    
    def query(self,stat,base,ctx):
        # 约定：同一 scope 下按 priority 顺序叠加。
        mods = self.get_effects(stat.scope)
        mods = sorted(mods,key=lambda m:m.priority)
        x = base 
        for m in mods:
            if m.op == "ADD":x += m.value
            elif m.op == "MUL":x *= m.value
            elif m.op == "OVERRIDE":x /= m.value
            elif m.op == "CLAMP":x = clamp(x,m.min,m.max)

def clamp(x, low, high):
    return max(low, min(x, high))
