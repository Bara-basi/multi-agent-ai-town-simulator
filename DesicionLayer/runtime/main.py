import asyncio 
import json
from agent.player import Player
from agent.agent_config import PLAYER_INFO
from agent.actions import ActionMethod
from agent.world import World
from server import AgentServer
from typing import Dict,Any,List
from agent.runtime import AgentManager,AgentRuntimeCtx,WsDispatcher
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
# async def observe_snapshot(ctx:AgentRuntimeCtx) -> Dict[str,Any]:
#     try:
#         obs = await format_prompt(player=ctx.player,action_history=ctx.actions_history,world=ctx.world)
#         return obs
#     except Exception:
#         logger.exception("format_prompt failed for %s", ctx.agent_id)
#         return {}



async def llm_plan(ctx:AgentRuntimeCtx,summary:str=None) -> str:
    if summary is not None:
        ctx.player.agent.prompt_builder.summary = summary
    plan = await asyncio.to_thread(ctx.player.agent.plan, ctx.player, ctx.world)
    return plan
    

async def llm_act(ctx:AgentRuntimeCtx,plan:str=None) -> List[Dict[str,Any]]:
    if plan is not None:
        ctx.player.agent.prompt_builder.plan = plan
    actions = await asyncio.to_thread(ctx.player.agent.act, ctx.player, ctx.world)
    return actions

async def llm_summary(ctx:AgentRuntimeCtx,plan:str=None) -> str:
    if plan is not None:
        ctx.player.agent.prompt_builder.plan = plan
    summary = await asyncio.to_thread(ctx.player.agent.reflect, ctx.player, ctx.world)
    ctx.player.agent.prompt_builder.summary = summary
    return summary

async def ws_link(ctx:AgentRuntimeCtx,action:Dict[str,Any]):
    status = await ctx.actionMethod.method_action(ctx,action)
    return status


async def main():

    # 清空上一轮的debug日志,删除debug_log/resp目录下的所有文件，但不删除目录
    import os
    import shutil
    resp_dir = "debug_log/resp"  
    prompt_dir = "debug_log/prompt"  
    if os.path.exists(resp_dir):
        shutil.rmtree(resp_dir)
        os.makedirs(resp_dir)
    if os.path.exists(prompt_dir):
        shutil.rmtree(prompt_dir)
        os.makedirs(prompt_dir)

    # 开启ws服务
    wsserver = AgentServer()
    await wsserver.start()

    # 初始化玩家
    players:List[Player] = [Player.from_raw(id=id+1,raw=raw,player_num=len(PLAYER_INFO)) for id,raw in enumerate(PLAYER_INFO.values())]
    
   
    # 初始化世界
    world = World(players=players)
    world_lock = asyncio.Lock()
    
    # 等待所有agent连接
    needed = [f"agent-{p.id}" for p in players]
    logger.info(f"Waiting for agents: {needed}")
    while not all(wsserver.is_connected(k) for k in needed):
        await asyncio.sleep(0.5)
    
    logger.info("All agents connected: {}".format(wsserver.connected_ids()))


    # 创建agent运行环境
    dispatcher = WsDispatcher(wsserver)

    ctxs = [AgentRuntimeCtx(actionMethod=ActionMethod(),agent_id=f"agent-{p.id}",player=p,world=world,world_lock=world_lock,dispatch=dispatcher,actions_history=[],plan=llm_plan,act=llm_act,summary=llm_summary,link=ws_link) for p in players]

    # 启动agent运行环境，并保持主协程存活
    mgr = AgentManager()
    await mgr.start(ctxs,tick_sleep=0.1)

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await mgr.stop()
        await wsserver.stop()

if __name__ == '__main__':
    asyncio.run(main())
