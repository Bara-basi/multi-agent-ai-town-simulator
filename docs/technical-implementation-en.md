# Technical Implementation

## Overview

This project does not use frameworks such as LangChain, AutoGen, CrewAI, or FastAPI. Instead, it is built directly on top of Python standard tooling, `asyncio`, `websockets`, the OpenAI API, and Unity. The reason is not anti-framework sentiment. It is that this project cares deeply about four things:

- whether world state is defined and controlled explicitly
- whether action boundaries are enforced by deterministic code
- whether the protocol between decision and execution layers remains transparent
- whether the runtime can reliably catch and recover from agent failures

For a project centered on closed-loop execution, state flow, and interpretability, owning the core runtime is more valuable than adding another abstraction layer.

## 1. Python Coroutine-Driven Multi-Agent Runtime

The core scheduler in the decision layer is built entirely on Python coroutines. Each agent has its own async loop, and the unified runtime advances them on a fixed tick through `plan -> act -> execute -> reflect`:

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

This gives three direct benefits:

- multiple agents can progress concurrently instead of serially
- model calls, WebSocket waits, and action execution can suspend naturally
- the system is mostly high-IO rather than CPU-heavy, which makes coroutines a better fit than threads

## 2. WebSocket RPC: Treating Unity as a Remote Action Service

Architecturally, `ExecutionLayer` is treated as a remote action endpoint. The decision layer never manipulates Unity objects directly. Instead, it sends commands through WebSocket and waits for completion feedback. This is not a full RPC framework, but it already behaves like one: request, unique ID, response, timeout, and failure handling.

For each action, the decision layer generates an `action_id` and stores a `Future` inside a pending table:

```python
action_id = str(uuid.uuid4())
fut = asyncio.get_running_loop().create_future()
self.pending[action_id] = fut
await ws.send(json.dumps(payload))
msg = await asyncio.wait_for(fut, timeout=20)
```

Unity completes the action and returns a `complete` message with the same `action_id`, after which the decision layer continues execution.

This design matters because:

- the decision layer and execution layer are fully decoupled
- actions have clear request-response semantics
- timeout, retry, logging, and failure handling can all be attached at the protocol level

## 3. Action-Space Registry

Instead of writing all actions as a giant `if/elif` chain, the system uses an explicit action registry. The core structure is simple: `_REGISTRY` maps action names to `Entry`, while `_ALIASES` maps aliases to canonical action names.

```python
@dataclass
class Entry:
    handler: ActionHandler
    validators: List[ActionValidator] = field(default_factory=list)

_REGISTRY: Dict[str, Entry] = {}
_ALIASES: Dict[str, str] = {}
```

Actions are registered through a decorator:

```python
def register(action_name: str, *, aliases=None, validators=None):
    def deco(fn: ActionHandler) -> ActionHandler:
        _REGISTRY[action_name] = Entry(handler=fn, validators=validators or [])
        for alias in aliases or []:
            _ALIASES[alias] = action_name
        return fn
    return deco
```

For example:

```python
@register(
    "buy",
    validators=[must_be_at(loc_id="location:market"), must_have_stock(), must_have_enough_money()],
)
async def handle_buy(ctx, act) -> ActionResult:
    ...
```

When the system executes an action, `ActionExecutor` first normalizes the model output into `_ActionView`, then proceeds in this order:

1. resolve the action name and normalize `name/type`
2. fetch the action entry with `get_entry(name)`
3. run validators one by one
4. stop immediately if any validator returns an error
5. call the handler only if all checks pass

In simplified form:

```python
act = self._normalize_action(action, **kwargs)
entry = get_entry(name)

for validator in entry.validators:
    maybe = validator(self.ctx, act)
    if maybe is not None:
        return maybe

return await entry.handler(self.ctx, act)
```

This registry brings several practical benefits:

- the action space is explicit and inspectable
- validation logic and execution logic are separated
- new actions can be added without touching the runtime loop
- the LLM only proposes actions; deterministic rules decide whether they are allowed into the world

At a systems level, it turns "model output" into a proposed action that must be reviewed, rather than a command that is executed immediately.

## 4. OpenAI API and JSON Hard Constraints

The project uses three separate model paths:

- `plan`: generate high-level turn plans
- `act`: generate structured JSON actions
- `reflect`: generate short reflection text

The most critical one is `act`. This uses the OpenAI API's JSON mode:

```python
if restrict == "json":
    kwargs["text"] = {"format": {"type": "json_object"}}
```

or:

```python
if restrict == "json":
    kwargs["response_format"] = {"type": "json_object"}
```

The key difference is this:

- **OpenAI JSON mode** constrains the model during sampling. The decoder is only allowed to continue along token paths that can still form valid JSON.
- **The "JSON output" promised by many frameworks** is often prompt wording, parsing, retrying, or post-hoc repair. It increases the chance of getting JSON, but it does not constrain the actual token sampling space.

That is a major distinction:

- the former is **generation-time constraint**
- the latter is usually **post-generation repair**

In an agent system, this matters a lot. Once an action output loses structural guarantees, the downstream execution chain breaks. That is why this project relies on three layers of reliability:

1. PromptBuilder clearly defines context and action boundaries
2. OpenAI JSON mode constrains output format during sampling
3. ActionExecutor performs deterministic rule validation afterward

The final `json.loads()` step only accepts fully structured action objects, not text that merely looks like JSON.

## 5. PromptBuilder: Translating World State into Decision Context

PromptBuilder is not just a string concatenator. It is a context construction layer that organizes:

- actor attributes
- location information
- market inventory and prices
- executed actions
- current plans
- previous plans
- random events
- action boundaries

into structured context blocks, then produces separate prompts for `plan / act / reflect`.

Its purpose is not to make prompts longer. Its purpose is to convert world state into stable decision semantics. For example:

- whether the actor is currently at the market
- whether `buy/sell` is currently allowed
- whether inventory is sufficient for `consume/sell`
- whether market stock is sufficient for `buy`
- whether current fatigue still allows further action

This reduces how much environmental logic the model has to infer on its own.

## 6. Memory, Reflection, and Replanning

`MemoryStore` records the day's plans and action results. Based on execution outcomes, the runtime decides:

- whether to continue the current plan
- whether to force replanning
- whether to trigger reflection

The result is:

- the agent can distinguish current-plan actions from old-plan history
- failed actions do not lead to blind repetition
- reflection becomes an input to the next planning cycle

This gives the agent a basic form of continuity instead of making every step an isolated model call.

## 7. World State and Rule System

The town is split into two layers:

- static definitions: CSV / JSON files for actors, locations, items, and events
- dynamic state: `WorldState / ActorState / LocationState` holding live runtime data

This makes content expansion easier while ensuring the runtime always works with a unified state interface.

## 8. Behavior Guards

To prevent agents from falling into useless loops, the runtime implements several guard mechanisms:

- repeated-action guard
- trade-churn guard
- split-action guard
- survival-priority guard

These safeguards do not depend on the model "figuring it out." They are enforced at the system level, which is far more important for long-running agents than single-prompt optimization.

## 9. Why No Framework

The project intentionally avoids agent frameworks and backend frameworks for three reasons:

- the main loop and world rules are highly customized
- action boundaries, execution feedback, and failure recovery need precise control
- for a portfolio project, low-level design ability carries more signal than framework familiarity

In other words, the project is meant to demonstrate not "I can use an agent framework," but "I can build a working agent system from scratch and make it run reliably."
