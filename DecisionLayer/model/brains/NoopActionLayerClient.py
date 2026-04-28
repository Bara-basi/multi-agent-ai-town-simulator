from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class NoopActionLayerClient:
    """Action-layer stub used when Unity integration is disabled."""

    def bind_world(self, world: Any) -> None:
        _ = world
        return None

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

    async def round_start(self, actor_id, round_index: int) -> bool:
        _ = actor_id, round_index
        return True

    async def round_end(self, actor_id, today_money_delta: int) -> bool:
        _ = actor_id, today_money_delta
        return True

    async def send_information(
        self,
        target: str,
        info: Dict[str, Any],
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        _ = target, info, agent_id, ws_conn
        return True

    def agent_information(self) -> Dict[str, Any]:
        return {"agents": []}

    async def broadcast_agent_information(
        self,
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        _ = agent_id, ws_conn
        return True

    async def wait_shop_stock_update(self, timeout_s: float = 120.0) -> Dict[str, Any] | None:
        _ = timeout_s
        return None

    def clear_stock_updates(self) -> None:
        return None

    async def consume(self, actor_id, item, value) -> bool:
        _ = actor_id, item, value
        return True

    async def sleep(self, actor_id, source=None) -> bool:
        _ = actor_id, source
        return True

    async def buy(self, actor_id, qty, money, source=None) -> bool:
        _ = actor_id, qty, money, source
        return True

    async def sell(self, actor_id, qty, money, source=None) -> bool:
        _ = actor_id, qty, money, source
        return True
