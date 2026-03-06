# 技术实现

## 总览

这个项目没有使用 LangChain、AutoGen、CrewAI、FastAPI 一类框架，而是直接基于 Python 标准库、`asyncio`、`websockets`、OpenAI API 和 Unity 自行搭建。原因不是排斥框架，而是这个项目更关心 4 件事：

- 世界状态是否由我自己定义并掌控
- 动作边界是否由确定性代码裁决
- 决策层和执行层之间的协议是否足够透明
- Agent 失败后能否被 runtime 稳定接住

对于这种强调闭环、状态流和可解释性的项目，自己把主干实现清楚，比引入一层额外抽象更合适。

## 1. Python 协程驱动多 Agent Runtime

决策层的核心调度完全建立在 Python 协程之上。每个 Agent 都有独立异步循环，由统一 runtime 以固定 tick 持续执行 `plan -> act -> execute -> reflect`：

```python
tasks = [
    asyncio.create_task(
        self._run_actor_loop(actor_id, interval_seconds, on_tick=on_tick),
        name=f"actor-{actor_id}",
    )
    for actor_id in target_ids
]
await asyncio.gather(*tasks)
```

这意味着：

- 多个 Agent 可以并发推进，而不是串行阻塞
- 模型调用、WebSocket 等待回执、动作执行都能自然挂起
- 整个系统主要是高 IO 场景，协程比线程更轻、更容易控制

## 2. WebSocket RPC：把 Unity 当作远端动作服务

`ExecutionLayer` 在架构上被我视为“远端执行端”。决策层不直接操作 Unity 对象，而是通过 WebSocket 发送命令、等待回执。这不是完整 RPC 框架，但已经具备典型 RPC 的行为特征：请求、唯一 ID、等待结果、超时处理、失败返回。

每次动作发送时，都会生成一个 `action_id`，然后把一个 `Future` 挂到 `pending` 表中：

```python
action_id = str(uuid.uuid4())
fut = asyncio.get_running_loop().create_future()
self.pending[action_id] = fut
await ws.send(json.dumps(payload))
msg = await asyncio.wait_for(fut, timeout=20)
```

Unity 侧完成动作后回传同一个 `action_id` 的 `complete` 消息，决策层收到后继续向下推进。

这套设计的价值在于：

- 决策层和执行层彻底解耦
- 动作具备确定的请求-回执语义
- 超时、失败、日志、重试都能挂在协议层

## 3. 动作空间注册表

这里没有把所有动作写成一串 `if/elif`，而是做成了一个显式的动作注册表。核心数据结构很简单：一个 `_REGISTRY` 存动作名到 `Entry` 的映射，一个 `_ALIASES` 处理别名映射。

```python
@dataclass
class Entry:
    handler: ActionHandler
    validators: List[ActionValidator] = field(default_factory=list)

_REGISTRY: Dict[str, Entry] = {}
_ALIASES: Dict[str, str] = {}
```

动作通过装饰器注册：

```python
def register(action_name: str, *, aliases=None, validators=None):
    def deco(fn: ActionHandler) -> ActionHandler:
        _REGISTRY[action_name] = Entry(handler=fn, validators=validators or [])
        for alias in aliases or []:
            _ALIASES[alias] = action_name
        return fn
    return deco
```

例如：

```python
@register(
    "buy",
    validators=[must_be_at(loc_id="location:market"), must_have_stock(), must_have_enough_money()],
)
async def handle_buy(ctx, act) -> ActionResult:
    ...
```

真正执行时，`ActionExecutor` 会先把模型输出归一化成统一视图 `_ActionView`，再按下面的顺序处理：

1. 解析动作名，统一 `name/type`
2. 用 `get_entry(name)` 从注册表中取出动作入口
3. 依次运行 validators
4. 只要有一个 validator 返回错误，动作立即终止
5. 全部通过后再调用 handler 修改世界状态

简化后大致是这样：

```python
act = self._normalize_action(action, **kwargs)
entry = get_entry(name)

for validator in entry.validators:
    maybe = validator(self.ctx, act)
    if maybe is not None:
        return maybe

return await entry.handler(self.ctx, act)
```

这个注册表机制有几个实际好处：

- 动作空间显式化，系统允许什么动作一眼可见
- 校验逻辑和执行逻辑分离，降低 handler 复杂度
- 新增动作时不需要侵入 runtime 主循环
- LLM 只负责提出动作，是否允许进入世界由规则系统裁决

本质上，它把“模型输出”变成了“待审查的动作提案”，而不是直接执行的命令。

## 4. OpenAI API 与 JSON 硬约束

项目里 `plan / act / reflect` 是三条不同调用链：

- `plan`：生成阶段性计划文本
- `act`：生成结构化 JSON 动作
- `reflect`：生成短反思文本

其中最关键的是 `act`。这里我用的是 OpenAI API 提供的 JSON mode：

```python
if restrict == "json":
    kwargs["text"] = {"format": {"type": "json_object"}}
```

或：

```python
if restrict == "json":
    kwargs["response_format"] = {"type": "json_object"}
```

这里要强调一个本质区别：

- **OpenAI JSON mode**：约束发生在模型采样阶段，解码器只允许模型继续生成能构成合法 JSON 的 token 路径。也就是说，模型不是“被提醒最好输出 JSON”，而是在采样时就被限制在 JSON 文法内部。
- **很多框架里的“JSON 输出”**：本质上往往只是 prompt 约束、输出解析器、重试器，或者先生成文本再做修复。它提高了得到 JSON 的概率，但没有从 token 采样层限制模型的输出空间。

这两者的差别非常大：

- 前者是 **生成时约束**
- 后者通常是 **生成后修补**

在 Agent 系统里，这个差异尤其重要。因为一旦动作输出不是结构化 JSON，runtime 后面整个动作执行链都会断掉。所以我更倾向于把可靠性建立在三层之上：

1. PromptBuilder 负责把上下文和动作边界说清楚
2. OpenAI JSON mode 在采样阶段约束输出格式
3. ActionExecutor 再做一次确定性规则校验

最后再统一做一次 `json.loads()`，确保 runtime 接收到的是结构化动作对象，而不是看起来像 JSON 的文本。

## 5. PromptBuilder：把世界状态翻译成决策上下文

PromptBuilder 并不是简单字符串拼接器，而是决策输入整理器。它会把：

- 角色属性
- 地点信息
- 市场库存与价格
- 已执行动作
- 当前计划
- 历史计划
- 随机事件
- 动作边界

整理成结构化上下文，再分别生成 `plan / act / reflect` 三类 prompt。

它的作用不是让 prompt 更长，而是提前完成“世界状态到决策语义”的翻译。例如：

- 当前是否在市场
- 是否允许 `buy/sell`
- 背包是否足够 `consume/sell`
- 库存是否足够 `buy`
- 当前疲劳值是否还适合继续行动

这一步本质上是在减少模型需要“自己补完环境规则”的负担。

## 6. 记忆、反思与重规划

`MemoryStore` 负责记录当日计划与动作结果。runtime 会根据执行结果决定：

- 是否继续当前计划
- 是否强制重规划
- 是否触发反思

这样做的结果是：

- Agent 能区分“当前计划内已执行动作”和“旧计划历史”
- 动作失败后不会机械重复
- 反思结果会进入下一轮计划输入

这让 Agent 具备了最基础的“连续性”，而不是每一步都像孤立调用。

## 7. 世界状态与规则系统

整个小镇采用“静态定义 + 动态状态”两层结构：

- 静态定义：CSV / JSON 描述角色、地点、物品和事件
- 动态状态：`WorldState / ActorState / LocationState` 持有实时运行数据

这种拆分让内容扩展更轻，也让 runtime 始终只面对统一状态接口。

## 8. 行为保护机制

为了防止 Agent 陷入无效循环，runtime 额外实现了几类保护：

- 重复动作保护
- 交易震荡保护
- 拆分动作保护
- 生存优先保护

这些机制不依赖模型“自己悟出来”，而是系统层主动兜底。对长期运行 Agent 来说，这类机制的价值往往高于单次 prompt 调优。

## 9. 为什么没有用框架

这个项目没有使用 Agent 框架或后端框架，核心原因有三点：

- 主循环和世界规则高度定制
- 需要精确控制动作边界、执行回执和失败恢复
- 作品集展示里，底层设计能力比框架熟练度更有信息量

换句话说，这个项目想展示的不是“我会调用某个 Agent 框架”，而是“我能从零搭建一个可运行的 Agent 系统，并让它稳定工作”。
