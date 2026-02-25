from __future__ import annotations

"""提示词构建器：把观察快照转换为 plan/act/reflect 三类 prompt。"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List
from datetime import datetime

@dataclass
class PromptSection:
    title: str
    content: str
    kind: str = "info"


@dataclass
class PromptPacket:
    prompt_type: str
    actor_id: str
    created_at: str
    sections: List[PromptSection]
    meta: Dict[str, Any]

    def render_for_llm(self) -> str:
        # 统一渲染逻辑，减少各 prompt 方法重复拼接字符串。
        parts: List[str] = []
        for section in self.sections:
            content = (section.content or "").strip()
            if not content and not section.title:
                continue
            if section.title:
                parts.append(f"{section.title}\n{content}".strip())
            else:
                parts.append(content)
        return "\n\n".join(parts).strip()


class PromptBuilder:
    def __init__(self) -> None:
        self.plan_txt: str = ""
        self.reflect_txt: str = ""
        self.error_log: str = ""

    def _mkdir(self, path: str) -> None:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

    def _sec(self, title: str, content: str, kind: str = "info") -> PromptSection:
        return PromptSection(title=title, content=(content or "").rstrip(), kind=kind)

    def _obs_actor_id(self, obs: Any) -> str:
        return str(getattr(obs, "act_id", getattr(obs, "actor_id", "")))

    def _packet(self, prompt_type: str, obs: Any, sections: List[PromptSection]) -> PromptPacket:
        # 统一 packet 元信息，便于调试日志对齐。
        actor_snapshot = getattr(obs, "actor_snapshot", {}) or {}
        day = getattr(obs, "day", 0)
        meta = {
            "day": day,
            "player_location": actor_snapshot.get("cur_location", ""),
        }
        return PromptPacket(
            prompt_type=prompt_type,
            actor_id=self._obs_actor_id(obs),
            created_at=str(day),
            sections=sections,
            meta=meta,
        )

    def _write_prompt_log(self, packet: PromptPacket) -> None:
        # 每次构造 prompt 时同步落盘 md/json，便于离线排查模型行为。
        base_dir = "debug_log/prompt"
        self._mkdir(base_dir)
        fname_base = f"turn{packet.created_at}_{packet.actor_id.split(':')[1]}"

        md_path = os.path.join(base_dir, f"{fname_base}.md")
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n--------------- {packet.prompt_type}/{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} --------------\n\n")
            f.write(packet.render_for_llm())

        json_path = os.path.join(base_dir, f"{fname_base}.json")
        with open(json_path, "a", encoding="utf-8") as f:
            json.dump(asdict(packet), f, ensure_ascii=False, indent=2)

    def _format_inventory(self, inventory_snapshot: Any) -> str:
        if inventory_snapshot is None:
            return "空"
        if isinstance(inventory_snapshot, str):
            return inventory_snapshot if inventory_snapshot.strip() else "空"
        if isinstance(inventory_snapshot, list):
            return "，".join(map(str, inventory_snapshot)) if inventory_snapshot else "空"
        if isinstance(inventory_snapshot, dict):
            if not inventory_snapshot:
                return "空"
            return "，".join(f"{k}x{v}" for k, v in inventory_snapshot.items())
        return str(inventory_snapshot)

    def _build_base_sections(self, obs: Any) -> List[PromptSection]:
        # 三类 prompt 共用的背景、规则、角色状态。
        actor = getattr(obs, "actor_snapshot", {}) or {}
        day = getattr(obs, "day", -1)

        background = (
            "你在一个小镇生存经营环境中行动。"
            "目标是保持生存属性安全，并逐步提升资金与资源。"
        )

        rules = "\n".join(
            [
                "- 仅依据当前提示中的信息决策，不要虚构物品、地点或规则。",
                "- 优先保证生存属性（饱食度、水分值、精神值）不低于20%。",
                "- 若关键信息不足，先移动到可获取信息的位置再行动。",
            ]
        )

        identity = f"角色：{actor.get('identity', '')}"
        location = f"当前位置：{actor.get('cur_location', '')}"
        money = f"金钱：{actor.get('money', 0)}"
        attrs = (
            f"属性：饱食度 {round(float(actor.get('hunger', 0.0)), 2)}，"
            f"水分值 {round(float(actor.get('thirst', 0.0)), 2)}，"
            f"精神值 {round(float(actor.get('fatigue', 0.0)), 2)}"
            " 三项属性越高约安全,最高为100,每回合结束时会扣减一定比例的属性"
        )
        inv = f"背包：{self._format_inventory(actor.get('inventory'))}"
        state = "\n".join([f"日期：{day}", identity, location, money, attrs, inv])

        return [
            self._sec("## 背景", background, "info"),
            self._sec("## 规则", rules, "rules"),
            self._sec("## 角色状态", state, "state"),
        ]

    def _format_locations_info(self, obs: Any) -> str:
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}

        lines: List[str] = []
        for loc_id, loc_obs in location_snapshot.items():
            loc_def = catalog_locations.get(loc_id, {})
            loc_name = loc_def.get("name", loc_id)
            loc_desc = loc_def.get("description") or loc_obs.get("desp", "")
            lines.append(f"- {loc_name} ({loc_id})：{loc_desc}")
        return "\n".join(lines) if lines else "- 暂无地点信息"

    def _find_market_location_id(self, obs: Any) -> str | None:
        # 优先看 runtime 快照中的 market 组件，找不到再用名称猜测。
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}

        for loc_id, loc_obs in location_snapshot.items():
            if isinstance(loc_obs, dict) and "market" in loc_obs:
                return loc_id
        for loc_id, loc_def in catalog_locations.items():
            name = str(loc_def.get("name", "")).lower()
            if "market" in name or "集市" in name:
                return loc_id
        return None

    def format_market_item_list(self, obs: Any) -> str:
        title = "### 市场商品"
        market_loc_id = self._find_market_location_id(obs)
        if not market_loc_id:
            return f"{title}\n- 当前未发现市场地点"

        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        market_obs = location_snapshot.get(market_loc_id, {}) or {}
        market_comp = market_obs.get("market", {}) or {}
        stock = market_comp.get("stock", {}) or {}
        prices = market_comp.get("price", {}) or {}

        items = (getattr(obs, "catalog_snapshot", {}) or {}).get("items", {}) or {}
        lines: List[str] = [title]

        for item_id, qty in stock.items():
            if qty is None or int(qty) <= 0:
                continue
            item = items.get(item_id, {})
            name = item.get("name", item_id)
            desc = item.get("description", "")
            base_price = float(item.get("base_price", 0) or 0)
            price = float(prices.get(item_id, base_price) or 0)

            if base_price > 0:
                ratio = price / base_price
                if ratio >= 1.3:
                    price_info = "显著偏贵"
                elif ratio <= 0.7:
                    price_info = "显著偏低"
                else:
                    price_info = "接近常规价格"
            else:
                price_info = "无基准价"

            lines.append(
                f"- {name}({item_id}) | 库存 {qty} | 价格 {price:.2f} | {price_info} | {desc}"
            )

        if len(lines) == 1:
            lines.append("- 当前无可交易商品")
        return "\n".join(lines)

    def _build_action_guide(self, obs: Any) -> str:
        # 通过明确输出约束，降低 LLM 产生非法动作的概率。
        actor = getattr(obs, "actor_snapshot", {}) or {}
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}

        cur_loc = actor.get("cur_location", "")
        home = actor.get("home", "")

        move_targets = sorted(set([str(loc_id) for loc_id in catalog_locations.keys()]))
        move_targets_text = "，".join(move_targets) if move_targets else "无"

        available_actions = ["move", "consume", "sleep", "buy", "sell", "wait", "finish"]

        lines = [
            "## 动作输出要求",
            "- 只输出 JSON 对象或 JSON 数组，不要输出额外文本。",
            "- 数组最多 3 步；若包含 move，建议只输出 move。",
            f"- 允许动作类型：{', '.join(available_actions)}。",
            "- 无安全动作时输出 {\"type\":\"finish\"}。",
            f"- 当前位置：{cur_loc}；家：{home}；可移动目标：{move_targets_text}。",
            "- trade 仅在市场地点执行，item 必须来自市场商品列表。",
            "- consume/cook 仅可使用背包已有物品。",
            "## 示例",
            '{"type":"move","target":"location:market"}',
            '{"type":"consume","item":"bread","qty":1}',
            '{"type":"sleep"}',
            '{"type":"buy","item":"bread","qty":2}',
            '{"type":"sell","item":"apple","qty":5}',
            '{"type":"finish"}',
        ]
        return "\n".join(lines)

    def get_top_level_plan(self, obs: Any) -> str:
        # 中期计划：给模型一个“接下来几小时”目标框架。
        sections: List[PromptSection] = []
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 上次反思", self.reflect_txt or "暂无", "memory"))
        sections.append(self._sec("## 地点信息", self._format_locations_info(obs), "state"))

        task = "\n".join(
            [
                "请制定接下来几个小时的计划。",
                "- 优先保障生存属性，再考虑收益。属性值越高代表越健康，最高为100",
                "- 仅依据已知信息，信息不足时写明先去哪里确认。",
                "- 输出 3-6 条可执行计划。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))

        packet = self._packet("plan", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()

    def get_local_action(self, obs: Any) -> str:
        # 局部动作决策：将当前地点上下文和短期记忆组合给模型。
        sections: List[PromptSection] = []
        sections += self._build_base_sections(obs)

        actor = getattr(obs, "actor_snapshot", {}) or {}
        cur_loc = actor.get("cur_location", "")
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}

        loc_def = catalog_locations.get(cur_loc, {})
        loc_obs = location_snapshot.get(cur_loc, {})
        loc_name = loc_def.get("name", cur_loc)
        loc_desc = loc_def.get("description") or loc_obs.get("desp", "")

        location_info = f"你当前在：{loc_name} ({cur_loc})\n地点描述：{loc_desc}"
        market_loc_id = self._find_market_location_id(obs)
        if cur_loc == market_loc_id:
            location_info = f"{location_info}\n\n{self.format_market_item_list(obs)}"
        sections.append(self._sec("## 当前地点信息", location_info, "state"))

        recent_events = getattr(obs, "working_events", []) or []
        if recent_events:
            mem = "\n".join([f"- {x}" for x in recent_events[-10:]])
        else:
            mem = "暂无近期事件"
        sections.append(self._sec("## 近期事件", mem, "memory"))

        sections.append(self._sec("## 当前计划", self.plan_txt or "暂无", "memory"))

        task = "\n".join(
            [
                "请基于当前计划与近期事件，输出下一步动作。",
                "输出 1-3 步；若计划完成，输出 finish，若需要结束回合，则输出wait。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))
        sections.append(self._sec("", self._build_action_guide(obs), "guide"))

        if self.error_log.strip():
            sections.append(self._sec("## 上一步错误", self.error_log, "error"))

        packet = self._packet("act", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()

    def get_reflection_and_summary(self, obs: Any) -> str:
        # 反思提示词：把近期事件压缩成可复用经验文本。
        sections: List[PromptSection] = []
        sections += self._build_base_sections(obs)

        recent_events = getattr(obs, "working_events", []) or []
        if recent_events:
            mem = "\n".join([f"- {x}" for x in recent_events[-20:]])
        else:
            mem = "暂无近期事件"
        sections.append(self._sec("## 近期事件", mem, "memory"))
        sections.append(self._sec("## 最近计划", self.plan_txt or "暂无", "memory"))

        task = "\n".join(
            [
                "请基于近期事件做简短总结与反思。",
                "- 只总结已发生的事，不要虚构。",
                "- 给出做得好的点和需要改进的点。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))

        packet = self._packet("summary", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()

    # Compatibility for AgentBrain current API
    def build_plan(self, obs: Any) -> str:
        return self.get_top_level_plan(obs)

    def build_act(self, obs: Any) -> str:
        return self.get_local_action(obs)

    def build_reflect(self, obs: Any) -> str:
        return self.get_reflection_and_summary(obs)
