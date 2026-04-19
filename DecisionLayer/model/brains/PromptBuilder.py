from __future__ import annotations

"""Prompt builder: convert observation snapshots into plan/act/reflect/decision prompts."""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List

from config.config import (
    ATTR_CN_MAP,
    FATIGUE_DECAY_PER_ACTION,
    FATIGUE_DECAY_PER_DAY,
    HUNGER_DECAY_PER_DAY,
    THIRST_DECAY_PER_DAY,
)


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
    STABLE_GLOBAL_POLICY = "\n".join(
        [
            "你在进行一个回合制生存交易游戏决策。",
            "你的唯一信息来源是当前提示词，不要虚构事实。",
            "先保命再赚钱：生存属性低时优先恢复。",
            "保持行动稳健，避免无意义重复操作。",
        ]
    )

    STABLE_OUTPUT_POLICY = "\n".join(
        [
            "输出要简洁、可执行、与任务严格对齐。",
            "禁止输出与任务无关的闲聊。",
        ]
    )

    STABLE_DECISION_PROTOCOL = "\n".join(
        [
            "决策协议：",
            "1) 先检查动作是否可执行（地点/库存/背包/数量）。",
            "2) 再检查生存安全（饱食度/水分值/精神值）。",
            "3) 最后执行收益动作。",
            "4) 若不确定，选择保守动作 wait。",
        ]
    )

    STABLE_DECISION_POINT_POLICY = "\n".join(
        [
            "你是“决策点代理（Decision Point Agent）",
            "你的任务是：基于当前状态，输出本回合决策点动作列表（可多次消耗决策点）。",
            "目标优先级：先保障生存，再提高盈利效率，再考虑信息优势。",
            "每个列表元素都只能在 4 个动作中 4 选 1：skip / exchange_cash / get_intel / lock_price。",
            "动作含义：",
            "- skip：不使用决策点。",
            "- exchange_cash：消耗1点决策点，兑换40元现金。",
            "- get_intel：消耗1点决策点，获取随机3个商品的明日价格情报,多次使用时不会重复获取同一商品。",
            "- lock_price：消耗1点决策点，锁定任意商品价格1回合。",
            "决策原则：",
            "- 决策点为0时只能选择 skip。",
            "- 决策点为3时即将溢出，建议至少消耗1点决策点。",
            "- 生存压力高且现金紧张时，优先 exchange_cash。",
            "- 有明确交易计划且信息价值高时，优先 get_intel。",
            "- 已有重点交易标的且希望规避短期波动时，优先 lock_price。",
            "- 无明确收益或风险对冲价值时，选择 skip。",
            "- 锁价优先于情报：若某商品被锁价，则该商品情报自动失效。",
            "- 可见性：get_intel 为私有信息，仅自己可见；lock_price 结果对其它Agent不可见。",
        ]
    )

    STABLE_DECISION_POINT_OUTPUT = "\n".join(
        [
            "必须严格输出单个 JSON 列表（array），禁止输出任何额外文本、Markdown 或代码块。",
            "列表元素 Schema（严格遵守）：",
            "{",
            '  "decision": "skip | exchange_cash | get_intel | lock_price",',
            '  "item": "string | null",',
            '  "reason": "string"',
            "}",
            "字段约束：",
            "- item 仅在 decision=lock_price 时可填写商品短ID（如 bread、water），其他情况必须为 null。",
            "- reason 用一句简短中文说明依据（生存压力/现金压力/价格风险/信息价值/决策点溢出）。",
            "- 列表元素允许重复（例如可连续两次 get_intel）。",
            "- 单回合最多输出3个元素；系统会按顺序逐条执行，决策点耗尽后后续元素自动失效。",
        ]
    )

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
        actor_id = (
            getattr(obs, "act_id", None)
            or getattr(obs, "actor_id", None)
            or (getattr(obs, "actor_snapshot", {}) or {}).get("id", "")
        )
        return str(actor_id or "unknown_actor")

    def _packet(self, prompt_type: str, obs: Any, sections: List[PromptSection]) -> PromptPacket:
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

    def _actor_suffix(self, actor_id: str) -> str:
        if ":" in actor_id:
            return actor_id.split(":", 1)[1] or "unknown"
        return actor_id or "unknown"

    def _write_prompt_log(self, packet: PromptPacket) -> None:
        base_dir = "debug_log/prompt"
        self._mkdir(base_dir)
        actor_suffix = self._actor_suffix(packet.actor_id)
        fname_base = f"round{packet.created_at}_{actor_suffix}"

        md_path = os.path.join(base_dir, f"{fname_base}.md")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n--------------- {packet.prompt_type}/{ts} --------------\n\n")
            f.write(packet.render_for_llm())

        jsonl_path = os.path.join(base_dir, f"{fname_base}.jsonl")
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(packet), ensure_ascii=False) + "\n")

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _normalize_item_id(self, item_id: str) -> str:
        if isinstance(item_id, str) and item_id.startswith("item:"):
            return item_id.split(":", 1)[1]
        return str(item_id)

    def _extract_inventory_map(self, obs: Any) -> Dict[str, int]:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        inv_map = actor.get("inventory_map", {}) or {}
        out: Dict[str, int] = {}
        if isinstance(inv_map, dict):
            for item_id, qty in inv_map.items():
                q = int(qty or 0)
                if q <= 0:
                    continue
                out[self._normalize_item_id(str(item_id))] = q
        return out

    def _extract_inventory_buy_price_map(self, obs: Any) -> Dict[str, float]:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        buy_price_map = actor.get("inventory_buy_price_map", {}) or {}
        out: Dict[str, float] = {}
        if isinstance(buy_price_map, dict):
            for item_id, price in buy_price_map.items():
                out[self._normalize_item_id(str(item_id))] = self._safe_float(price, 0.0)
        return out

    def _stable_prefix_sections(self) -> List[PromptSection]:
        return [
            self._sec("## 全局约束", self.STABLE_GLOBAL_POLICY, "rules"),
            self._sec("## 输出约束", self.STABLE_OUTPUT_POLICY, "rules"),
            self._sec("## 决策协议", self.STABLE_DECISION_PROTOCOL, "rules"),
        ]

    def _build_events_and_buffs_block(self, obs: Any) -> str:
        world_events = getattr(obs, "world_events", []) or []
        actor_buffs = getattr(obs, "actor_buffs", []) or []
        world_text = "；".join(world_events) if world_events else "无"
        buff_text = "；".join(actor_buffs) if actor_buffs else "无"
        return "\n".join(
            [
                f"- 当前世界事件：{world_text}",
                f"- 当前角色Buff：{buff_text}",
            ]
        )

    def _build_base_sections(self, obs: Any) -> List[PromptSection]:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        day = int(getattr(obs, "day", -1) or -1)

        background = (
            "你在一个AI小镇中进行生存与贸易博弈。"
            "目标是在生存属性不归零的前提下，尽快把现金提升到10000元。"
        )

        rules = "\n".join(
            [
                "- 仅依据当前提示词信息决策，不得补充设定。",
                "- 饱食度/水分值/精神值任一归零会出局。",
                "- 非必要不冒险，避免高消耗低收益动作。",
            ]
        )

        identity = f"角色：{actor.get('identity', '未知')}"
        location = f"当前位置：{actor.get('cur_location', '未知')}"
        money = f"金钱：{self._safe_float(actor.get('money'), 0.0):.2f}/10000元"
        attrs = (
            f"属性：饱食度[{self._safe_float(actor.get('hunger'), 0.0):.2f}/100]，"
            f"水分值[{self._safe_float(actor.get('thirst'), 0.0):.2f}/100]，"
            f"精神值[{self._safe_float(actor.get('fatigue'), 0.0):.2f}/100]"
        )
        inv = f"背包：{actor.get('inventory', '空') or '空'}"
        inv_qty_map = self._extract_inventory_map(obs)
        inv_buy_price_map = self._extract_inventory_buy_price_map(obs)
        avg_cost_parts: List[str] = []
        for short_item_id, qty in sorted(inv_qty_map.items()):
            if qty <= 0:
                continue
            if short_item_id in inv_buy_price_map:
                avg_price = self._safe_float(inv_buy_price_map.get(short_item_id), 0.0)
                avg_cost_parts.append(f"{short_item_id}:{avg_price:.2f}元")
            else:
                avg_cost_parts.append(f"{short_item_id}:未知")
        inv_avg_cost = "，".join(avg_cost_parts) if avg_cost_parts else "无"

        state = "\n".join([f"日期：第{day}天", identity, location, money, attrs, inv, f"背包平均买入价：{inv_avg_cost}"])

        return [
            self._sec("## 背景", background, "info"),
            self._sec("## 规则", rules, "rules"),
            self._sec("## 角色状态", state, "state"),
            self._sec("## 当前事件与Buff", self._build_events_and_buffs_block(obs), "state"),
        ]

    def _format_locations_info(self, obs: Any) -> str:
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}

        lines: List[str] = []
        for loc_id in sorted(location_snapshot.keys()):
            loc_obs = location_snapshot.get(loc_id, {}) or {}
            loc_def = catalog_locations.get(loc_id, {}) or {}
            loc_name = loc_def.get("name", loc_id)
            loc_desc = loc_def.get("description") or loc_obs.get("desp", "")
            lines.append(f"- {loc_name} ({loc_id})：{loc_desc}")
        return "\n".join(lines) if lines else "- 暂无地点信息"

    def format_market_item_list(self, obs: Any) -> str:
        title = "### 市场商品"
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        market_loc = (location_snapshot.get("location:market", {}) or {}).get("market", {}) or {}
        stock = market_loc.get("stock", {}) or {}
        cur_price = market_loc.get("price", {}) or {}
        items = (getattr(obs, "catalog_snapshot", {}) or {}).get("items", {}) or {}

        lines: List[str] = [title]
        for item_id in sorted(stock.keys()):
            qty = int(stock.get(item_id, 0) or 0)
            if qty <= 0:
                continue

            item = items.get(item_id, {}) or {}
            short_id = self._normalize_item_id(item_id)
            name = item.get("name", short_id)
            desc = item.get("description", "")
            effects_raw = item.get("effects", {}) or {}
            effects: List[str] = []
            for attr_name, value in effects_raw.items():
                if value != 0:
                    sign = "+" if value > 0 else "-"
                    effects.append(f"{ATTR_CN_MAP.get(attr_name, attr_name)}{sign}{value}")

            effect_text = f"；效果：{', '.join(effects)}" if effects else ""
            base_price = self._safe_float(item.get("base_price"), 0.0)
            price = self._safe_float(cur_price.get(item_id), 0.0)
            sell_ratio = self._safe_float(item.get("sell_ratio"), 0.0)
            if base_price > 0:
                ratio = price / base_price
                if ratio >= 1.3:
                    level_text = "相比均价显著偏贵，偏向卖出"
                elif ratio <= 0.7:
                    level_text = "相比均价显著偏低，偏向买入"
                elif ratio >= 1.1:
                    level_text = "相比均价略贵"
                elif ratio <= 0.9:
                    level_text = "相比均价略低"
                else:
                    level_text = "接近常规价格"
            else:
                level_text = "无基准价"

            lines.append(
                f"- {name}({short_id})：库存 {qty}，现价 {price:.2f}元，出售折价 {sell_ratio:.2f}，{level_text}；{desc}{effect_text}"
            )

        if len(lines) == 1:
            lines.append("- 当前无可交易商品")
        lines.append("出售折价说明：出售价格=买入价格*出售折价。")
        lines.append("输出说明：item 字段请填写短ID（如 bread、water），不要带 item: 前缀。")
        return "\n".join(lines)

    def _build_action_guide(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        cur_loc = actor.get("cur_location", "")
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}
        move_targets = sorted(str(loc_id) for loc_id in catalog_locations.keys())
        move_targets_text = "；".join(move_targets) if move_targets else "无"

        lines = [
            "## 动作输出要求",
            "- 只输出一个JSON对象，不要额外文本。",
            "- 允许动作：move/consume/sleep/buy/sell/wait。",
            "- buy/sell 仅在 location:market 执行。",
            "- consume 仅可使用背包已有物品。",
            f"- 当前位置信息：{cur_loc}；可移动目标：{move_targets_text}。",
            f"- 除 sleep/wait 外每次动作消耗 {FATIGUE_DECAY_PER_ACTION} 点精神值。",
            f"- 每回合结束：精神值恢复 {-FATIGUE_DECAY_PER_DAY}，饱食度减少 {HUNGER_DECAY_PER_DAY}，水分值减少 {THIRST_DECAY_PER_DAY}。",
        ]
        return "\n".join(lines)

    def _build_decision_point_plan_context(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        private_ctx = getattr(obs, "decision_private_context", {}) or {}
        dp = int(actor.get("decision_point", 0) or 0)
        dp_max = int(actor.get("decision_point_max", 3) or 3)

        lines: List[str] = [
            f"- 你的当前决策点：{dp}/{dp_max}",
            "- 什么是决策点？每回合回复一点的稀有货币，有你之前的Agent决定是否使用。"
            "- 锁价优先于情报：若商品已被其它玩家锁价，则该商品的明日价格情报自动失效。",
        ]
        private_note = str(private_ctx.get("private_note", "") or "")
        if private_note:
            lines.append(f"- 决策点执行结果：{private_note}")

        executed_actions = list(private_ctx.get("executed_actions", []) or [])
        if executed_actions:
            reasons: List[str] = []
            for row in executed_actions:
                r = str((row or {}).get("reason", "") or "").strip()
                if r and r not in reasons:
                    reasons.append(r)
            if reasons:
                lines.append(f"- 你本回合决策理由摘要：{'；'.join(reasons)}")
            lines.append("- 你本回合已执行的决策点动作序列：")
            for idx, row in enumerate(executed_actions, start=1):
                d = str((row or {}).get("decision", "skip"))
                item = (row or {}).get("locked_item") or (row or {}).get("item")
                item_text = f", item={item}" if item else ""
                lines.append(f"  - #{idx}: {d}{item_text}")

        cash_delta = float(private_ctx.get("cash_delta", 0.0) or 0.0)
        if cash_delta != 0:
            lines.append(f"- 决策点现金变动：{cash_delta:+.2f} 元")

        locked_items = list(private_ctx.get("locked_items", []) or [])
        if locked_items:
            lines.append(f"- 你已锁定商品：{', '.join(str(x) for x in locked_items)}（全局生效1回合，但其它Agent不可见）")

        intel_rows = list(private_ctx.get("intel", []) or [])
        if intel_rows:
            lines.append("- 你获取的明日价格情报：")
            valid_rows = [row for row in intel_rows if bool(row.get("valid", False))]
            if not valid_rows:
                lines.append("  - 暂无可用情报")
            for row in intel_rows:
                if not bool(row.get("valid", False)):
                    continue
                item = row.get("item", "unknown")
                acc = float(row.get("accuracy", 0.0) or 0.0)
                intel_price = float(row.get("intel_price", 0.0) or 0.0)
                trend = str(row.get("trend", "明日趋势未知") or "明日趋势未知")
                lines.append(f"  - {item}：情报价 {intel_price:.2f}，{trend}，情报正确率 {acc:.2f}")
        else:
            lines.append("- 你本回合没有明日价格情报。")
        return "\n".join(lines)

    def get_top_level_plan(self, obs: Any) -> str:
        sections: List[PromptSection] = []
        sections += self._stable_prefix_sections()
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 决策点上下文", self._build_decision_point_plan_context(obs), "state"))
        sections.append(self._sec("## 上次反思", self.reflect_txt or "暂无", "memory"))
        sections.append(self._sec("## 地点信息", self._format_locations_info(obs), "state"))
        sections.append(self._sec("## 物价信息", self.format_market_item_list(obs), "prices_info"))

        task = "\n".join(
            [
                "请制定本回合行动计划。",
                "- 先保生存，再追求利润。",
                "- 交易时结合“背包平均买入价”和当前市场价评估浮盈亏。",
                "- 计划最多4步（不含回合结束）。",
                "- 给出可执行步骤，不要虚构结果。",
                "- 目标完成或信息不足时，最后一步写“回合结束”。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))

        packet = self._packet("plan", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()

    def get_local_action(self, obs: Any) -> str:
        sections: List[PromptSection] = []
        sections += self._stable_prefix_sections()
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 决策点上下文", self._build_decision_point_plan_context(obs), "state"))

        actor = getattr(obs, "actor_snapshot", {}) or {}
        cur_loc = actor.get("cur_location", "")
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}

        loc_def = catalog_locations.get(cur_loc, {}) or {}
        loc_obs = location_snapshot.get(cur_loc, {}) or {}
        loc_name = loc_def.get("name", cur_loc)
        loc_desc = loc_def.get("description") or loc_obs.get("desp", "")

        location_info = f"你当前在：{loc_name} ({cur_loc})\n地点描述：{loc_desc}"
        if cur_loc == "location:market":
            location_info = f"{location_info}\n\n{self.format_market_item_list(obs)}"
        sections.append(self._sec("## 当前地点信息", location_info, "state"))

        sections.append(self._sec("## 当前计划", self.plan_txt or "暂无", "memory"))
        sections.append(self._sec("## 本回合执行记录", getattr(obs, "memory_current_plan", "") or "暂无", "memory"))

        task = "\n".join(
            [
                "根据当前计划与状态，输出下一步单个动作JSON。",
                "- 先检查动作可执行性，再考虑收益。",
                "- 若计划已完成或不适用，输出 wait。",
                "- 若上一步失败，必须改动作或参数。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))
        sections.append(self._sec("## 动作空间", self._build_action_guide(obs), "guide"))

        if self.error_log.strip():
            sections.append(self._sec("## 上一步错误", self.error_log, "error"))

        packet = self._packet("act", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()

    def get_reflection_and_summary(self, obs: Any) -> str:
        sections: List[PromptSection] = []
        sections += self._stable_prefix_sections()
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 本回合已执行动作与结果", getattr(obs, "memory", "") or "暂无", "memory"))

        task = "\n".join(
            [
                "请做简短反思，用于下一回合优化。",
                "- 仅总结已发生事实，不要虚构。",
                "- 输出最多3条，每条一句。",
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

    def decision_point_prompt(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        day = int(getattr(obs, "day", 0) or 0)
        decision_point = int(actor.get("decision_point", 0) or 0)
        decision_point_max = int(actor.get("decision_point_max", 3) or 3)
        money = self._safe_float(actor.get("money"), 0.0)
        hunger = self._safe_float(actor.get("hunger"), 0.0)
        thirst = self._safe_float(actor.get("thirst"), 0.0)
        fatigue = self._safe_float(actor.get("fatigue"), 0.0)
        cur_loc = str(actor.get("cur_location", "unknown"))

        inventory_map = self._extract_inventory_map(obs)
        inventory_text = ", ".join(f"{k}:{v}" for k, v in sorted(inventory_map.items())) if inventory_map else "空"

        catalog_items = (getattr(obs, "catalog_snapshot", {}) or {}).get("items", {}) or {}
        item_short_ids = sorted(self._normalize_item_id(item_id) for item_id in catalog_items.keys())
        lock_item_hint = ", ".join(item_short_ids) if item_short_ids else "暂无可用商品ID"

        sections: List[PromptSection] = []
        # Front-load stable text to improve cache hit.
        sections.append(self._sec("## 身份与机制", self.STABLE_DECISION_POINT_POLICY, "rules"))
        sections.append(self._sec("## 输出格式", self.STABLE_DECISION_POINT_OUTPUT, "rules"))

        # Reuse existing prompt blocks.
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 地点信息", self._format_locations_info(obs), "state"))
        sections.append(self._sec("## 市场信息", self.format_market_item_list(obs), "prices_info"))

        decision_state = "\n".join(
            [
                f"- 现金：{money:.2f}/10000 元",
                f"- 决策点：{decision_point}/{decision_point_max}（每回合+1，上限3）",
                f"- 生存属性：饱食度 {hunger:.2f}/100，水分值 {thirst:.2f}/100，精神值 {fatigue:.2f}/100",
                f"- 背包（短ID:数量）：{inventory_text}",
                f"- 锁价可选商品短ID：{lock_item_hint}",
            ]
        )
        sections.append(self._sec("## 当前决策上下文", decision_state, "state"))
        sections.append(self._sec("## 上回合执行记录", getattr(obs, "memory", "") or "暂无", "memory"))

        task = "\n".join(
            [
                "基于上述信息，输出本回合的决策点动作列表（JSON array）。",
                "- 列表长度建议 1~3；可为空时请返回 [ {\"decision\":\"skip\",\"item\":null,\"reason\":\"...\"} ]。",
                "- 列表元素允许重复（如连续两次 get_intel）。",
                "- 仅返回 JSON 列表，不要任何额外文本。",
            ]
        )
        sections.append(self._sec("## 任务", task, "task"))

        packet = self._packet("decision_point", obs, sections)
        self._write_prompt_log(packet)
        return packet.render_for_llm()
