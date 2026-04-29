import asyncio
import csv
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict
from config.config import FATIGUE_DECAY_PER_DAY,HUNGER_DECAY_PER_DAY,THIRST_DECAY_PER_DAY
from runtime.load_data import HUMAN_SHOP_ASSISTANT_ACTOR_ID, load_catalog

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
    stock_updates: asyncio.Queue = field(default_factory=asyncio.Queue)
    _market_info_cache: Dict[str, Any] | None = None
    _agent_info_cache: Dict[str, Any] | None = None
    _system_warning_active: set[str] = field(default_factory=set)
    world: Any = None

    def bind_world(self, world: Any) -> None:
        self.world = world
        self._market_info_cache = None
        self._agent_info_cache = None
        self._system_warning_active.clear()

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
                    single_agent_id = msg.get("agent_id")
                    agent_ids = msg.get("agent_ids")

                    bound_ids = []
                    if isinstance(agent_ids, list):
                        for a in agent_ids:
                            a = str(a or "").strip()
                            if a:
                                self.connections[a] = ws
                                bound_ids.append(a)
                    else:
                        single_agent_id = str(single_agent_id or "").strip()
                        if single_agent_id:
                            self.connections[single_agent_id] = ws
                            bound_ids.append(single_agent_id)

                    if not bound_ids:
                        logger.warning("hello message missing agent_id/agent_ids")
                        continue

                    agent_id = bound_ids[0]
                    await ws.send(json.dumps({"type": "hello_ack", "server_time": int(time.time())}))
                    await self.send_information(
                        target="market",
                        info=self.market_information(),
                        ws_conn=ws,
                    )
                    if self.world is not None:
                        await self.broadcast_agent_information(ws_conn=ws)
                elif msg_type in {"ack", "pong"}:
                    continue
                elif msg_type == "complete":
                    action_id = msg.get("action_id")
                    fut = self.pending.pop(action_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    logger.info("[%s] complete action=%s status=%s", msg.get("agent_id"), action_id, msg.get("status"))
                elif msg_type == "shop_stock_update":
                    info = msg.get("info")
                    try:
                        msg["parsed_info"] = json.loads(info) if isinstance(info, str) else info
                    except Exception:
                        logger.exception("Failed to parse shop stock update info: %s", info)
                        msg["parsed_info"] = info
                    await self.stock_updates.put(msg)
                    logger.info("[%s] shop stock update received", msg.get("agent_id"))
                else:
                    logger.warning("Unknown message type: %s", msg_type)
        except Exception as e:
            logger.error("WebSocket connection error: %s", e)
        finally:
            disconnected = [aid for aid, conn in list(self.connections.items()) if conn == ws]
            for aid in disconnected:
                self.connections.pop(aid, None)
            if disconnected:
                logger.info("WebSocket disconnected agent_ids=%s", disconnected)

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
                for ws in set(self.connections.values()):
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

    def market_information(self) -> Dict[str, Any]:
        if self.world is not None:
            try:
                market = self.world.locations["location:market"].market()
                items = []
                for item_id, item_def in self.world.catalog.items.items():
                    items.append(
                        {
                            "itemId": item_id,
                            "name": item_def.name,
                            "purchasePrice": float(getattr(item_def, "purchase_price", item_def.base_price)),
                            "basePrice": float(market.price(item_id)),
                            "quantity": int(market.stock(item_id)),
                            "priceLocked": bool(market.is_price_locked_today(item_id)),
                        }
                    )
                player = {}
                human_actor = self.world.actors.get(HUMAN_SHOP_ASSISTANT_ACTOR_ID)
                if human_actor is not None:
                    current_money = float(getattr(human_actor, "money", 0.0) or 0.0)
                    last_money = float(getattr(self.world, "shop_assistant_last_money", current_money) or current_money)
                    player = {
                        "currentMoney": current_money,
                        "todayIncome": current_money - last_money,
                    }
                return {"items": items, "player": player}
            except Exception:
                logger.exception("Failed to build market info from world state; falling back to csv")

        if self._market_info_cache is not None:
            return self._market_info_cache

        csv_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "item.csv")
        )
        items = []
        try:
            rows = None
            for enc in ("utf-8-sig", "gbk"):
                try:
                    with open(csv_path, newline="", encoding=enc) as csvfile:
                        rows = list(csv.DictReader(csvfile))
                    break
                except UnicodeDecodeError:
                    rows = None

            for row in rows or []:
                name = str(row.get("name", "") or "").strip()
                if not name:
                    continue
                try:
                    purchase_price = float(
                        row.get("purchasePrice", row.get("purchase_price", row.get("basePrice", 0))) or 0
                    )
                except Exception:
                    purchase_price = 0.0
                try:
                    base_price = float(row.get("basePrice", 0) or 0)
                except Exception:
                    base_price = 0.0
                try:
                    quantity = int(float(row.get("quantity", 0) or 0))
                except Exception:
                    quantity = 0
                items.append(
                    {
                        "name": name,
                        "purchasePrice": purchase_price,
                        "basePrice": base_price,
                        "quantity": quantity,
                        "priceLocked": False,
                    }
                )
        except Exception:
            logger.exception("Failed to load market info from csv: %s", csv_path)
            items = []

        self._market_info_cache = {
            "items": items,
            "player": {
                "currentMoney": 1000,
                "todayIncome": 0,
            },
        }
        return self._market_info_cache

    @staticmethod
    def _actor_attr_value(actor: Any, attr_name: str) -> float:
        attrs = getattr(actor, "attrs", None) or {}
        attr = attrs.get(attr_name) if isinstance(attrs, dict) else None
        if attr is None:
            return 0.0
        try:
            return float(getattr(attr, "current", 0.0) or 0.0)
        except Exception:
            return 0.0

    def agent_information(self) -> Dict[str, Any]:
        if self.world is not None:
            try:
                agents = []
                for actor_id, agent_code in self.actor2agent.items():
                    if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
                        continue
                    actor = self.world.actors.get(actor_id)
                    if actor is None:
                        continue

                    actor_def = None
                    try:
                        actor_def = self.world.catalog.actor(actor_id)
                    except Exception:
                        actor_def = None

                    agent_name = str(getattr(actor_def, "name", "") or actor_id)
                    money = float(getattr(actor, "money", 0.0) or 0.0)
                    hunger = self._actor_attr_value(actor, "hunger")
                    fatigue = self._actor_attr_value(actor, "fatigue")
                    thirst = self._actor_attr_value(actor, "thirst")
                    agents.append(
                        {
                            "actorId": actor_id,
                            "agentCode": agent_code,
                            "agentName": agent_name,
                            "hungerValue": hunger,
                            "fatigueValue": fatigue,
                            "waterValue": thirst,
                            "money": money,
                            # Backend field aliases for future consumers.
                            "hunger": hunger,
                            "fatigue": fatigue,
                            "thirst": thirst,
                        }
                    )

                self._agent_info_cache = {"agents": agents}
                return self._agent_info_cache
            except Exception:
                logger.exception("Failed to build agent info from world state; falling back to cache")

        if self._agent_info_cache is not None:
            return self._agent_info_cache

        agents = []
        for actor_id, agent_code in self.actor2agent.items():
            if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
                continue
            agents.append(
                {
                    "actorId": actor_id,
                    "agentCode": agent_code,
                    "agentName": actor_id,
                    "hungerValue": 80,
                    "fatigueValue": 80,
                    "waterValue": 80,
                    "money": 1000,
                    "hunger": 80,
                    "fatigue": 80,
                    "thirst": 80,
                }
            )
        self._agent_info_cache = {"agents": agents}
        return self._agent_info_cache

    async def send_information(
        self,
        target: str,
        info: Dict[str, Any],
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        try:
            payload = {
                "type": "information",
                "target": target,
                "info": json.dumps(info, ensure_ascii=False),
            }
            if agent_id:
                payload["agent_id"] = agent_id

            if ws_conn is not None:
                await ws_conn.send(json.dumps(payload, ensure_ascii=False))
                return True

            if agent_id:
                ws = self.connections.get(agent_id)
                if not ws:
                    logger.warning("WebSocket connection not found for information push: %s", agent_id)
                    return False
                await ws.send(json.dumps(payload, ensure_ascii=False))
                return True

            targets = set(self.connections.values())
            if not targets:
                logger.warning("WebSocket connection not found for information broadcast")
                return False
            for ws in targets:
                await ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            logger.exception("Failed to push information message to %s", agent_id)
            return False

    async def broadcast_agent_information(
        self,
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        sent = await self.send_information(
            target="agents",
            info=self.agent_information(),
            agent_id=agent_id,
            ws_conn=ws_conn,
        )
        if ws_conn is None:
            await self.broadcast_system_warnings()
        return sent

    async def broadcast_message(
        self,
        source: str,
        message: str,
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        source = str(source or "").strip()
        message = str(message or "").strip()
        if not source or not message:
            return False
        return await self.send_information(
            target="messages",
            info={"messages": [{"source": source, "message": message}]},
            agent_id=agent_id,
            ws_conn=ws_conn,
        )

    async def broadcast_messages(
        self,
        messages: list[Dict[str, Any]],
        agent_id: str | None = None,
        ws_conn: Any | None = None,
    ) -> bool:
        cleaned = []
        for row in messages or []:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source") or "").strip()
            message = str(row.get("message") or "").strip()
            if source and message:
                cleaned.append({"source": source, "message": message})
        if not cleaned:
            return False
        return await self.send_information(
            target="messages",
            info={"messages": cleaned},
            agent_id=agent_id,
            ws_conn=ws_conn,
        )

    async def broadcast_system_warnings(self) -> None:
        if self.world is None:
            return
        messages = []
        attr_labels = {
            "hunger": "饥饿值",
            "fatigue": "体力值",
            "thirst": "水分值",
        }
        for actor_id, agent_code in self.actor2agent.items():
            if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
                continue
            actor = self.world.actors.get(actor_id)
            if actor is None:
                continue
            try:
                actor_def = self.world.catalog.actor(actor_id)
                actor_name = str(getattr(actor_def, "name", "") or agent_code)
            except Exception:
                actor_name = agent_code

            for attr_name, attr_label in attr_labels.items():
                value = self._actor_attr_value(actor, attr_name)
                key = f"{actor_id}:attr:{attr_name}:low"
                if value < 20:
                    if key not in self._system_warning_active:
                        messages.append({
                            "source": "系统",
                            "message": f"注意，{actor_name}的{attr_label}已低于20%",
                        })
                        self._system_warning_active.add(key)
                else:
                    self._system_warning_active.discard(key)

            money = float(getattr(actor, "money", 0.0) or 0.0)
            money_key = f"{actor_id}:money:high"
            if money > 8000:
                if money_key not in self._system_warning_active:
                    messages.append({
                        "source": "系统",
                        "message": f"注意，{actor_name}的资金已高于8000",
                    })
                    self._system_warning_active.add(money_key)
            else:
                self._system_warning_active.discard(money_key)

        if messages:
            await self.broadcast_messages(messages)

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

    @staticmethod
    def _short_item_id(item: Any) -> str:
        item_id = getattr(item, "id", item)
        item_id = str(item_id or "").strip()
        if item_id.startswith("item:"):
            item_id = item_id.split(":", 1)[1]
        return item_id or "item"

    async def round_start(self, actor_id, round_index: int) -> bool:
        agent_id = self.actor2agent.get(actor_id)
        if not agent_id:
            logger.warning("Actor is not bound to agent_id: %s", actor_id)
            return False
        result = await self.send(
            type="command",
            agent_id=agent_id,
            cmd="round_start",
            value=max(0, int(round_index)),
        )
        ok = self.is_success(result)
        if ok:
            await self.broadcast_message("系统", f"第{max(0, int(round_index))}回合开始")
        return ok

    async def round_end(self, actor_id, today_money_delta: int) -> bool:
        agent_id = self.actor2agent.get(actor_id)
        if not agent_id:
            logger.warning("Actor is not bound to agent_id: %s", actor_id)
            return False
        result = await self.send(
            type="command",
            agent_id=agent_id,
            cmd="round_end",
            value=max(-10000, min(10000, int(today_money_delta))),
        )
        ok = self.is_success(result)
        if ok:
            await self.broadcast_message("系统", f"回合结束，本回合收入{int(today_money_delta)}")
        return ok
    
    async def consume(self, actor_id,item,value):
        item_animation = self._short_item_id(item)
        result = await self.show_animation(actor_id=actor_id, animation=item_animation, value=-value)
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

    async def buy(self,actor_id,qty,money,source=None,item_id=None):
        item_animation = self._short_item_id(item_id)
        result = await self.show_animation(actor_id=actor_id,animation=item_animation,value=qty)
        result &= await self.move(actor_id=actor_id,source=source,target="收银台")
        result &= await self.show_animation(actor_id=actor_id,animation="money",value=-money)
        return result
    
    async def sell(self,actor_id,qty,money,source=None,item_id=None):
        item_animation = self._short_item_id(item_id)
        result = await self.move(actor_id=actor_id,source=source,target="收银台")
        result &= await self.show_animation(actor_id=actor_id,animation="money",value=money)
        result &= await self.show_animation(actor_id=actor_id,animation=item_animation,value=-qty)
        return result


    def is_success(self,result) -> bool:
        return isinstance(result, dict) and result.get("status") == "ok"
    def is_connected(self, agent_id: str) -> bool:
        return agent_id in self.connections

    def connected_ids(self):
        return list(self.connections.keys())

    async def wait_shop_stock_update(self, timeout_s: float = 120.0) -> Dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self.stock_updates.get(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for shop stock update")
            return None

    def clear_stock_updates(self) -> None:
        while True:
            try:
                self.stock_updates.get_nowait()
            except asyncio.QueueEmpty:
                break


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


async def main() -> None:
    """
    Start the websocket server, send market info, start a round, then wait for shop stock submission.
    Unity's WsAgentClient default agent_id is "Agent-1"; override with WS_TEST_AGENT_ID if needed.
    """
    catalog = load_catalog()
    actor_id = next(iter(catalog.actors.keys()))
    agent_id = os.getenv("WS_TEST_AGENT_ID", "Agent-1")
    server = WebSocketServer(actor2agent={actor_id: agent_id})

    logger.info("Shop stock update test starting. actor_id=%s agent_id=%s", actor_id, agent_id)
    logger.info("Start Unity client and wait for hello with agent_id=%s", agent_id)

    await server.start()
    try:
        await _wait_agent_connected(server, agent_id, timeout_s=120.0)
        logger.info("Agent connected: %s", agent_id)

        logger.info("[TEST] sending market information")
        await server.send_information(
            target="market",
            info=server.market_information(),
            agent_id=agent_id,
        )

        logger.info("[TEST] sending round_start")
        await server.round_start(actor_id=actor_id, round_index=1)

        logger.info("[TEST] waiting for player stock submission")
        update = await server.wait_shop_stock_update(timeout_s=300.0)
        if update is not None:
            print(json.dumps(update.get("parsed_info", update), ensure_ascii=False, indent=2))
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(main())
