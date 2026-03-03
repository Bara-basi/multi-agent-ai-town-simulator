import asyncio,json,uuid,time
import websockets
from typing import Dict,Any,Optional
import logging
logger = logging.getLogger(__name__)

class AgentServer:
    def __init__(self,host:str = "127.0.0.1",port:int = 9876,ping_interval:float=10.0):
        self.host = host
        self.port = port
        self.ping_interval = ping_interval
        self.agents:Dict[str,Any] = {}
        self.pending:Dict[str,asyncio.Future] = {}
        self._server:Optional[Any] = None
        self._ping_task:Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle,self.host,self.port)
        self._ping_task = asyncio.create_task(self._ping_loop(),name="ws-ping-loop")

    async def stop(self) -> None:
        """停止 ping 循环并关闭服务器与所有连接。"""
        # 先停 ping
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        # 主动关闭所有已知连接
        for aid, ws in list(self.agents.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self.agents.clear()

        # 关闭服务器
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("WS server closed")

        # 将所有未完成 action 标记为取消/超时，避免悬挂
        for aid, fut in list(self.pending.items()):
            if not fut.done():
                fut.set_result(None)
        self.pending.clear()

    async def _handle(self, ws):
        """
        单连接的收发处理
        """
        agent_id = None
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {raw}")
                    continue

                t = msg.get("type")
                if t == "hello":
                    agent_id = msg.get("agent_id", f"anon-{id(ws)}")
                    self.agents[agent_id] = ws
                    await ws.send(json.dumps({"type": "hello_ack", "server_time": int(time.time())}))
                    logger.info(f"[CONNECTED] {agent_id}")
                elif t == "ack":
                    pass
                elif t == "complete":
                    aid = msg.get("action_id")
                    fut = self.pending.pop(aid, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    logger.info(f"[DONE] {msg.get('agent_id')} {aid} status={msg.get('status')}")
                elif t == "pong":
                    pass
                else:
                    logger.warning(f"[WARN] unknown msg type: {t}")

        except Exception as e:
            logger.error(f"Connection closed: {agent_id},{e}")
        finally:
            # 清理登记（仅移除该连接，不整站停服）
            if agent_id and self.agents.get(agent_id) is ws:
                del self.agents[agent_id]
                logger.info(f"[DISCONNECTED] {agent_id}")
        
    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                for aid, ws in list(self.agents.items()):
                    try:
                        await ws.send(json.dumps({"type": "ping"}))
                    except Exception:
                        self.agents.pop(aid, None)
        except asyncio.CancelledError:
            pass


    async def send_action(
        self,
        agent_id: str,
        cmd: str = "",
        target: str = "",
        cur_location = "",
        value:float  = 0,
        timeout: float = 25.0,
        type:str = "command",
    ) -> Optional[dict]:
        """
        发送一条 action 给前端（例如 go_to），并等待 'complete' 回包。
        成功返回 complete 消息（dict），超时/失败返回 None。
        """
        ws = self.agents.get(agent_id)
        if not ws:
            logger.warning(f"Agent {agent_id} not found")
            
            return None

        action_id = str(uuid.uuid4())
        payload = {
            "type": type,
            "cur_location":cur_location,
            "agent_id": agent_id,
            "action_id": action_id,
            "cmd": cmd,
            "target": target,
            "value": value,
        }

        fut = asyncio.get_running_loop().create_future()
        self.pending[action_id] = fut

        await ws.send(json.dumps(payload))
        logger.info(f"[SEND] -> {agent_id} {action_id} {cmd} {target}")

        try:
            msg = await asyncio.wait_for(fut, timeout=timeout)
            return msg 
        except asyncio.TimeoutError:
            self.pending.pop(action_id, None)
            logger.warning(f"[TIMEOUT] {agent_id} {action_id} {cmd} {target}")
            return None

    def is_connected(self, agent_id: str) -> bool:
        return agent_id in self.agents

    def connected_ids(self):
        return list(self.agents.keys())       



async def main():
    server = AgentServer()
    await server.start()
    while not all(server.is_connected(k) for k in ["agent-1","agent-2","agent-3","agent-4"]):
        await asyncio.sleep(0.5)
    print("All agents connected:",server.connected_ids())
    # await server.send_action("agent-1","go_to",target="收银台",cur_location="家")
    # await server.send_action("agent-1","go_to",target="家",cur_location="收银台")
    await server.send_action("agent-1","sleeping",value = 5)
    # await server.send_action("agent-1","waiting",value = 5)
    # await server.send_action("agent-1","go_to",target="钓鱼点",cur_location="集市")
    await asyncio.sleep(1)
        
if __name__ == '__main__':
    asyncio.run(main())
    
