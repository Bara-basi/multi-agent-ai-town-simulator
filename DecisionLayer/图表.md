# AITown Decision Layer（图表导向说明）

> 这份 README 只提供快速上手视角，重点是帮助外部读者看懂代码主流程与模块关系。

## 1) 系统总览（模块与数据流）

```mermaid
flowchart LR
    subgraph Data[静态数据]
        A1[data/actor.csv]
        A2[data/item.csv]
        A3[data/location.csv]
    end

    A1 --> B[load_catalog]
    A2 --> B
    A3 --> B

    B --> C[Catalog]
    C --> D[build_state]
    D --> E[WorldState]

    E --> F[AgentRuntime]
    F --> G[Agent]
    G --> H[PromptBuilder]
    G --> I[LLM]

    F --> J[ActionExecutor]
    J --> K[action_registry]
    K --> L[validators]
    K --> M[handlers]

    H --> N[debug_log/prompt/*.md]
    M --> E
```

## 2) Agent 决策时序图（单个 Actor 的一次 tick）

```mermaid
sequenceDiagram
    participant RT as AgentRuntime
    participant WS as WorldState
    participant AG as Agent
    participant PB as PromptBuilder
    participant LLM as OpenAIModel
    participant EX as ActionExecutor
    participant AR as ActionRegistry

    RT->>WS: observe(actor_id)
    WS-->>RT: Observation

    alt 需要重新计划(_should_plan=true)
        RT->>AG: plan(obs)
        AG->>PB: build_plan(obs)
        PB-->>AG: plan prompt
        AG->>LLM: agenerate(plan)
        LLM-->>AG: plan text
    end

    loop act + execute（含重试/重规划）
        RT->>AG: act(obs)
        AG->>PB: build_act(obs)
        PB-->>AG: action prompt
        AG->>LLM: agenerate(json)
        LLM-->>AG: action json

        RT->>EX: execute(action, actor_id)
        EX->>AR: get_entry(name)
        AR-->>EX: validators + handler
        EX-->>RT: ActionResult
    end

    opt 需要反思(_should_reflect=true)
        RT->>AG: reflect(obs)
        AG->>PB: build_reflect(obs)
        PB-->>AG: reflect prompt
        AG->>LLM: agenerate(reflect)
        LLM-->>AG: reflect text
    end
```


## 4) 核心类图（精简版）

```mermaid
classDiagram
    class WorldState {
      +Catalog catalog
      +int day
      +Dict actors
      +Dict locations
      +observe(actor_id) Dict
      +update_day() None
    }

    class AgentRuntime {
      +tick_actor(actor_id) ActionResult
      +run(interval_seconds, actor_ids, on_tick) None
      -_obs(actor_id) Observation
      -_force_replan_after_error(actor_id, st, reason)
    }

    class Agent {
      +ActorId id
      +LLM model
      +PromptBuilder prompt_builder
      +plan(obs) None
      +act(obs) Dict
      +reflect(obs) None
    }

    class PromptBuilder {
      +string plan_txt
      +string reflect_txt
      +string error_log
      +build_plan(obs) string
      +build_act(obs) string
      +build_reflect(obs) string
    }

    class ActionExecutor {
      +execute(action, actor_id) ActionResult
      -_normalize_action(action) _ActionView
    }

    class ActorState {
      +ActorId id
      +float money
      +LocationId location
      +Inventory inventory
      +MemoryStore memory
      +Dict attrs
      +bool running
      +update_day() None
    }

    class LocationState {
      +LocationId id
      +Dict component
      +market() MarketComponent
      +observe() Dict
      +update_day(catalog) None
    }

    class MarketComponent {
      +Dict _stock
      +Dict _price
      +Dict _next_price
      +init_stock(catalog) None
      +price(item_id) float
      +stock(item_id) int
      +update_day(catalog) None
    }

    class MemoryStore {
      +List act_records
      +int current_plan_id
      +start_plan(plan_id, plan_text) None
      +add_action(message, plan_id, status, code, finish) None
      +observe() string
      +observe_current_plan() string
      +observe_previous_plans() string
    }

    class ActionResult {
      +bool status
      +string code
      +string message
      +bool finish
    }

    WorldState --> ActorState
    WorldState --> LocationState
    WorldState --> AgentRuntime
    AgentRuntime --> Agent
    AgentRuntime --> ActionExecutor
    Agent --> PromptBuilder
    Agent --> LLM
    ActionExecutor --> ActionResult
    ActorState --> MemoryStore
    LocationState --> MarketComponent
```

## 5) 交易回合状态图（行为约束视角）

```mermaid
stateDiagram-v2
    [*] --> Planning
    Planning --> Acting

    Acting --> Validate: 生成动作
    Validate --> Execute: 校验通过
    Validate --> Replan: 校验失败/重复保护/交易震荡保护

    Execute --> Acting: 执行成功且未收尾
    Execute --> Replan: 执行失败
    Execute --> Reflecting: 满足反思触发条件

    Replan --> Acting: 重新规划后继续
    Reflecting --> Acting: 继续下一步
    Acting --> EndTurn: 输出 wait

    EndTurn --> DailySettle: 所有 actor running=false
    DailySettle --> Planning: day+1
```

## 6) 建议在后续补充的图（可选）

```mermaid
flowchart LR
    O[WorldState.observe] --> P[PromptBuilder packet]
    P --> Q[LLM 输入]
    Q --> R[Action/Plan/Reflect 输出]
    R --> S[ActionExecutor]
    S --> T[MemoryStore.add_action]
    P --> U[debug_log/prompt]
    T --> O
```

如果你希望，我可以下一步把这份图表 README 再拆成两层：
1. 面向阅读者（超短版）
2. 面向开发者（含“改动作/改提示词/改市场”的定位导航）
