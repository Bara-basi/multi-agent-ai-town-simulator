from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class NoopActionLayerClient:
    """Action-layer stub used when Unity integration is disabled."""

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def is_connected(self, agent_id: str) -> bool:
        _ = agent_id
        return True

    def connected_ids(self) -> List[str]:
        return []

    async def move(self, actor_id, source, target) -> bool:
        _ = actor_id, source, target
        return True

    async def update_state(self, actor_id, state_name, value) -> bool:
        _ = actor_id, state_name, value
        return True

    async def show_animation(self, actor_id, animation, value) -> bool:
        _ = actor_id, animation, value
        return True

    async def consume(self, actor_id, item, value) -> bool:
        _ = actor_id, item, value
        return True

    async def sleep(self, actor_id) -> bool:
        _ = actor_id
        return True

    async def buy(self, actor_id, qty, money) -> bool:
        _ = actor_id, qty, money
        return True

    async def sell(self, actor_id, qty, money) -> bool:
        _ = actor_id, qty, money
        return True
