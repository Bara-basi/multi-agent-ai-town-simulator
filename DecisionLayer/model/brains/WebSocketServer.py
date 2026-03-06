import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict
from config.config import FATIGUE_DECAY_PER_DAY,HUNGER_DECAY_PER_DAY,THIRST_DECAY_PER_DAY
from runtime.load_data import load_catalog

import websockets

logger = logging.getLogger(__name__)


@dataclass
class WebSocketServer:
    host: str = "127.0.0.1"
    port: int = 9876
    ping_interval: float = 10.0
    _server: Any = None
    _ping_task: asyncio.Task | None = None
    connections: Dict[str, Any] = field(default_factory=dict)
    actor2agent: Dict[str, str] = field(default_factory=dict)
    pending: Dict[str, asyncio.Future] = field(default_factory=dict)

    async def _handle(self, ws):
        agent_id = None
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("JSON message parse failed: %s", raw)
                    continue

                msg_type = str(msg.get("type", "")).strip()
                if msg_type == "hello":
                    agent_id = msg.get("agent_id")
                    if not agent_id:
                        logger.warning("hello message missing agent_id")
                        continue
                    self.connections[agent_id] = ws
                    await ws.send(json.dumps({"type": "hello_ack", "server_time": int(time.time())}))
                elif msg_type in {"ack", "pong"}:
                    continue
                elif msg_type == "complete":
                    action_id = msg.get("action_id")
                    fut = self.pending.pop(action_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    logger.info("[%s] complete action=%s status=%s", msg.get("agent_id"), action_id, msg.get("status"))
                else:
                    logger.warning("Unknown message type: %s", msg_type)
        except Exception as e:
            logger.error("WebSocket connection error: %s", e)
        finally:
            if agent_id and self.connections.get(agent_id) == ws:
                self.connections.pop(agent_id, None)
                logger.info("WebSocket disconnected: %s", agent_id)

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle, self.host, self.port)
        self._ping_task = asyncio.create_task(self._ping_loop(), name="ws-ping-pong")

    async def stop(self) -> None:
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        for ws in list(self.connections.values()):
            try:
                await ws.close()
            except Exception:
                pass
        self.connections.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_result(None)
        self.pending.clear()

        logger.info("WebSocket server stopped")

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                for ws in list(self.connections.values()):
                    try:
                        await ws.send(json.dumps({"type": "ping"}))
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass

    async def send(
        self,
        type: str,
        agent_id: str,
        cmd: str = None,
        target: str = None,
        value: float | None = None,
        cur_location: str | None = None,
    ):  
       
        logger.debug(
            "Sending message to agent %s: type=%s cmd=%s target=%s value=%s cur_location=%s",
            agent_id,
            type,
            cmd,
            target,
            value,
            cur_location,
        )
        ws = self.connections.get(agent_id)
        if not ws:
            logger.warning("WebSocket connection not found: %s", agent_id)
            return None

        action_id = str(uuid.uuid4())
        payload = {
            "type": type,
            "agent_id": agent_id,
            "action_id": action_id,
        }
        if cur_location:
            payload["cur_location"] = cur_location
        if value is not None:
            payload["value"] = value
        if target:
            payload["target"] = target
        if cmd:
            payload["cmd"] = cmd

        fut = asyncio.get_running_loop().create_future()
        self.pending[action_id] = fut
        await ws.send(json.dumps(payload))
        # await asyncio.sleep(0.2)  

        try:
            msg = await asyncio.wait_for(fut, timeout=20)
            return msg
        except asyncio.TimeoutError:
            self.pending.pop(action_id, None)
            logger.warning("WebSocket message timeout: %s", agent_id)
            return None

    async def move(self, actor_id, source, target)->bool:
        agent_id = self.actor2agent.get(actor_id)
        if not agent_id:
            logger.warning("Actor is not bound to agent_id: %s", actor_id)
            return False
        result = await self.send(
            type="command",
            agent_id=agent_id,
            cmd="go_to",
            target=target,
            cur_location=source,
        )
        return self.is_success(result)

    async def update_state(self, actor_id,state_name, value)->bool:
        agent_id = self.actor2agent.get(actor_id)
        if not agent_id:
            logger.warning("Actor agent_id: %s 未找到", actor_id)
            return False
        result = await self.send(
            type="command",
            agent_id=agent_id,
            cmd=state_name,
            value=value,
        )
        print("sleeping")
        return self.is_success(result)

    async def show_animation(self, actor_id, animation, value)->bool:
        agent_id = self.actor2agent.get(actor_id)
        if not agent_id:
            logger.warning("Actor is not bound to agent_id: %s", actor_id)
            return False
        result = await self.send(
            type="animation",
            agent_id=agent_id,
            target=animation,
            value=value,
        )
        return self.is_success(result)
    
    async def consume(self, actor_id,item,value):
        result = await self.show_animation(actor_id=actor_id, animation="item", value=-value)
        for attr_name,attr_value in (item.effects or {}).items():
            if attr_value != 0:
                result &= await self.show_animation(actor_id=actor_id,animation=attr_name,value=attr_value)
        return result

    
    async def sleep(self,actor_id,source):
        result = await self.move(actor_id=actor_id,source=source,target="床")
        if not result:
            return False
        result &= await self.update_state(actor_id=actor_id,state_name="sleeping",value=5)
        result &= await self.show_animation(actor_id=actor_id,animation="fatigue",value=-FATIGUE_DECAY_PER_DAY)
        result &= await self.show_animation(actor_id=actor_id,animation="hunger",value=-HUNGER_DECAY_PER_DAY)
        result &= await self.show_animation(actor_id=actor_id,animation="thirst",value=-THIRST_DECAY_PER_DAY)
        return result

    async def buy(self,actor_id,qty,money,source):
        result = await self.show_animation(actor_id=actor_id,animation="item",value=qty)
        result &= await self.move(actor_id=actor_id,source=source,target="收银台")
        result &= await self.show_animation(actor_id=actor_id,animation="money",value=-money)
        return result
    
    async def sell(self,actor_id,qty,money,source):
        result = await self.move(actor_id=actor_id,source=source,target="收银台")
        result &= await self.show_animation(actor_id=actor_id,animation="money",value=money)
        result &= await self.show_animation(actor_id=actor_id,animation="item",value=-qty)
        return result


    def is_success(self,result) -> bool:
        return isinstance(result, dict) and result.get("status") == "ok"
    def is_connected(self, agent_id: str) -> bool:
        return agent_id in self.connections

    def connected_ids(self):
        return list(self.connections.keys())


async def _wait_agent_connected(server: WebSocketServer, agent_id: str, timeout_s: float = 60.0) -> None:
    start = time.time()
    while not server.is_connected(agent_id):
        if time.time() - start > timeout_s:
            raise TimeoutError(f"Waited {timeout_s}s but {agent_id} is not connected")
        await asyncio.sleep(0.5)


async def _run_case(name: str, fn) -> bool:
    try:
        result = await fn()
        success = result if isinstance(result, bool) else (result is not None)
        logger.info("[TEST] %-18s -> result=%s success=%s", name, result, success)
        return bool(success)
    except Exception:
        logger.exception("[TEST] %-18s -> exception", name)
        return False

async def run_smoke_test_main() -> None:
    """
    连通测试代码
    """
    catalog = load_catalog()
    actor_id = next(iter(catalog.actors.keys()))
    agent_id = "agent-1"
    actor2agent = {actor_id: agent_id}
    server = WebSocketServer(actor2agent=actor2agent)

    unit_price = 100
 
    logger.info("Smoke test starting. actor_id=%s agent_id=%s", actor_id, agent_id)
    logger.info("Please start Unity client and send hello with agent_id=%s", agent_id)

    await server.start()
    try:
        await _wait_agent_connected(server, agent_id, timeout_s=120.0)
        logger.info("Agent connected: %s", agent_id)

        cases = [
            ("consume", lambda: server.consume(actor_id=actor_id, item=catalog.item("item:water"), value=1)),
            ("move", lambda: server.move(actor_id=actor_id, source="家", target="床")),
    
            ("show_animation", lambda: server.show_animation(actor_id=actor_id, animation="hunger", value=-1)),            ("buy", lambda: server.buy(actor_id=actor_id, qty=1, money=unit_price,source="家")),
            ("sell", lambda: server.sell(actor_id=actor_id, qty=1, money=unit_price)),
            ("move", lambda: server.move(actor_id=actor_id, source="集市", target="家")),
            ("update_state", lambda: server.update_state(actor_id=actor_id, state_name="sleeping", value=1)),
            ("sleep", lambda: server.sleep(actor_id=actor_id,source="家")),


        ]

        passed = 0
        for name, fn in cases:
            ok = await _run_case(name, fn)
            passed += int(ok)

        logger.info("Smoke test completed: %s/%s cases ran.", passed, len(cases))
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_smoke_test_main())
