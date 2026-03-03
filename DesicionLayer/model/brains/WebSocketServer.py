import asyncio,json,uuid,time
import websockets
from dataclasses import dataclass,field
from typing import Optional,List,Any,Dict
import logging

logger = logging.getLogger(__name__)

@dataclass
class WebSocketServer:
    host:str = "127.0.0.1"
    port:int = 9876
    ping_interval:float=10.0
    _server:Any = None
    _ping_task:asyncio.Task = None
    connections:Dict[str,Any] = field(default_factory=dict)
    actor2agent:Dict[str,Any] = field(default_factory=dict)
    pending:Dict[str,asyncio.Future] = field(default_factory=dict)
    async def _handle(self, ws):
        agent_id = None 
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"JSON消息解析失败: {raw}")
                t = msg.get("type")
                if t == "hello":
                    agent_id = msg["agent_id"]
                    self.connections[agent_id] = ws
                    await ws.send(json.dumps({"type":"hello_ack","server_time":int(time.time())}))
                elif t == "ack" or t == "pong":
                    pass 
                elif t == " complete":
                    aid = msg.get("action_id")
                    fut = self.pending.pop(aid,None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    logger.info(f"[None] {msg.get('agent_id')}{aid},状态：{msg.get('status')}")
                else:
                    logger.warning(f"[WARN] 未知消息类型: {t}")
        except Exception as e:
            logger.error(f"WebSocket连接异常: {e}")
        finally:
            if agent_id and self.connections.get(agent_id) == ws:
                self.connections.pop(agent_id)
                logger.info(f"WebSocket连接关闭: {agent_id}")


    async def start(self) -> None:
        self._server = await websockets.serve(self._handle, self.host, self.port)
        self._ping_task =asyncio.create_task(self._ping_loop(),name="ws-ping-pong")

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
            except:
                pass 
        self.connections.clear()
        
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None 
        logger.info("WebSocket服务器已停止")
        
        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_result(None)
        self.pending.clear()
    
    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                for ws in list(self.connections.values()):
                    try:
                        await ws.send(json.dumps({"type":"ping"}))
                    except:
                        pass
        except asyncio.CancelledError:
            pass

    async def send(
        self,
        type:str,
        agent_id:str,
        cmd:str,
        target:str,
        value:float = None,
        cur_location:str = None
    ):
        ws = self.connections("agent_id")
        if not ws:
            logger.warning(f"WebSocket连接不存在: {agent_id}")
            return None
        action_id = str(uuid.uuid4())
        payload = {
            "type":type,
            "agent_id":agent_id,
            "action_id":action_id,
            "cmd":cmd,
            "target":target,
        }
        if cur_location:
            payload["cur_location"] = cur_location
        if value:
            payload["value"] = value
        fut = asyncio.get_running_loop().create_future()
        self.pending[action_id] = fut
        await ws.send(json.dumps(payload))
        try:
            msg = await asyncio.wait_for(fut,timeout=20)
            return msg
        except asyncio.TimeoutError:
            logger.warning(f"WebSocket消息超时: {agent_id}")
            return None
    
    async def move(self,actor_id,source,target):
        return await self.send(
            type="command",
            agent_id=self.Actor2Connection[actor_id],
            cmd="target",
            target=target,
            cur_location=source            
        )
        return res
    
    async def update_state(self,actor_id,target,value):
        return await self.send(
            type="command",
            agent_id=self.Actor2Connection[actor_id],
            cmd="update_state",
            target=target,
            value=value
        )
    
    async def show_animation(self,actor_id, animation,value):
        return await self.send(
            typ="animation",
            agent_id=self.Actor2Connection[actor_id],
            cmd=animation,
            value=value
        )
    

    def is_connected(self,agent_id:str) -> bool:
        return agent_id in self.connections
    
    def connected_ids(self):
        return list(self.connections.keys())
    
