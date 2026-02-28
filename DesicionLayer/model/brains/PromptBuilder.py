from __future__ import annotations

"""提示词构建器：把观察快照转换为 plan/act/reflect 三类 prompt。"""

import json
import math
import os
import re
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
    # 这两段放在最前，尽量保持跨回合、跨任务恒定，以提高前缀缓存命中。
    STABLE_GLOBAL_POLICY = "\n".join(
        [
            "你在进行一个回合制生存交易游戏决策。",
            "你的唯一信息来源是当前提示词，不要虚构任何事实。",
            "先保命再赚钱：生存属性低时必须优先恢复。",
            "保持行动稳健，避免无意义重复操作。",
            "如果信息不足或计划无法安全执行，采用保守动作（wait）。",
        ]
    )

    STABLE_OUTPUT_POLICY = "\n".join(
        [
            "输出要简洁、可执行、与当前任务严格对齐。",
            "禁止输出与任务无关的解释、闲聊或角色扮演文本。",
            "禁止机械重复上一动作；若上一动作失败，必须换一个可执行动作。",
            "在执行计划前先做边界检查：地点、库存、背包三项任一不满足时，必须改动作。",
            "buy/sell/consume 同类同物品动作应一次完成，避免拆成多次小 qty。",
            "任何动作都要考虑体力成本：若收益不明确或步骤过碎，优先更少动作的方案。",
        ]
    )
    STABLE_DECISION_PROTOCOL = "\n".join(
        [
            "决策协议(固定)：",
            "1) 先检查动作是否合法（地点/库存/背包/数量）。",
            "2) 再检查生存安全（饱食/水分/精神）。",
            "3) 最后才执行计划步骤。",
            "4) 同一回合同一物品只能单向交易：只买或只卖，禁止买卖对冲。",
            "5) 若计划与现实状态冲突，立即放弃该计划步骤，改为可执行动作。",
            "6) 若无安全且可执行动作，输出 wait 结束回合。",
            "7) consume 先算不溢出的最大 qty，再决定是否执行；禁止无意义补满。",
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
        fname_base = f"turn{packet.created_at}_{actor_suffix}"

        md_path = os.path.join(base_dir, f"{fname_base}.md")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n--------------- {packet.prompt_type}/{ts} --------------\n\n")
            f.write(packet.render_for_llm())

        # 使用 jsonl 便于持续 append 且不破坏结构。
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

    def _extract_market_stock_map(self, obs: Any) -> Dict[str, int]:
        location_snapshot = getattr(obs, "location_snapshot", {}) or {}
        market_loc = (location_snapshot.get("location:market", {}) or {}).get("market", {}) or {}
        stock = market_loc.get("stock", {}) or {}
        out: Dict[str, int] = {}
        if isinstance(stock, dict):
            for item_id, qty in stock.items():
                q = int(qty or 0)
                if q < 0:
                    q = 0
                out[self._normalize_item_id(str(item_id))] = q
        return out

    def _catalog_items(self, obs: Any) -> Dict[str, Dict[str, Any]]:
        return (getattr(obs, "catalog_snapshot", {}) or {}).get("items", {}) or {}

    def _item_name_to_short_id(self, obs: Any) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for item_id, item in self._catalog_items(obs).items():
            short_id = self._normalize_item_id(str(item_id))
            name = str((item or {}).get("name", "")).strip()
            if name:
                out[name] = short_id
            out[short_id] = short_id
        return out

    def _parse_current_plan_stats(self, obs: Any) -> Dict[str, Any]:
        text = str(getattr(obs, "memory_current_plan", "") or "")
        name_to_short = self._item_name_to_short_id(obs)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        action_lines = [ln for ln in lines if not ln.startswith("[")]

        by_item: Dict[str, Dict[str, int]] = {}

        def touch(item: str) -> Dict[str, int]:
            k = name_to_short.get(item.strip(), self._normalize_item_id(item.strip()))
            if k not in by_item:
                by_item[k] = {
                    "buy_qty": 0,
                    "sell_qty": 0,
                    "consume_qty": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "consume_count": 0,
                }
            return by_item[k]

        for line in action_lines:
            m = re.search(r"你购买了\s*`?([^`\n]+?)`?\s*x\s*(\d+)", line)
            if m:
                stat = touch(m.group(1))
                qty = max(1, int(m.group(2)))
                stat["buy_qty"] += qty
                stat["buy_count"] += 1
                continue

            m = re.search(r"你出售了\s*`?([^`\n]+?)`?\s*x\s*(\d+)", line)
            if m:
                stat = touch(m.group(1))
                qty = max(1, int(m.group(2)))
                stat["sell_qty"] += qty
                stat["sell_count"] += 1
                continue

            m = re.search(r"你使用了\s*(\d+)\s*个\s*([^\n`]+)", line)
            if m:
                qty = max(1, int(m.group(1)))
                stat = touch(m.group(2))
                stat["consume_qty"] += qty
                stat["consume_count"] += 1

        high_cost_steps = 0
        for line in action_lines:
            if any(key in line for key in ("移动到", "购买了", "出售了", "使用了")):
                high_cost_steps += 1

        return {
            "action_lines": action_lines,
            "last_action_line": action_lines[-1] if action_lines else "",
            "high_cost_steps": high_cost_steps,
            "by_item": by_item,
        }

    def _build_trade_direction_guard(self, obs: Any) -> str:
        stats = self._parse_current_plan_stats(obs)
        by_item = stats["by_item"]
        bought: List[str] = []
        sold: List[str] = []
        mixed: List[str] = []
        for item, item_stat in sorted(by_item.items()):
            b = item_stat.get("buy_qty", 0)
            s = item_stat.get("sell_qty", 0)
            if b > 0 and s > 0:
                mixed.append(item)
            elif b > 0:
                bought.append(f"{item}x{b}")
            elif s > 0:
                sold.append(f"{item}x{s}")

        lines = ["## 回合内交易方向锁"]
        lines.append(f"- 本计划已买入：{'、'.join(bought) if bought else '无'}")
        lines.append(f"- 本计划已卖出：{'、'.join(sold) if sold else '无'}")
        if mixed:
            lines.append(f"- 警告：已出现买卖混合物品 {', '.join(mixed)}，下一步必须停止该物品交易并收口。")
        lines.append("- 规则：已买入过的物品本回合禁止卖出；已卖出过的物品本回合禁止买入。")
        lines.append("- 规则：同类同物品若已执行过一次，默认视为本回合该物品最后一次操作，除非存在明确生存风险。")
        return "\n".join(lines)

    def _build_consumption_guard(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        attrs = {
            "hunger": self._safe_float(actor.get("hunger"), 0.0),
            "thirst": self._safe_float(actor.get("thirst"), 0.0),
            "fatigue": self._safe_float(actor.get("fatigue"), 0.0),
        }
        targets = {"hunger": 75.0, "thirst": 75.0, "fatigue": 60.0}
        inventory_map = self._extract_inventory_map(obs)
        items = self._catalog_items(obs)

        lines: List[str] = ["## consume 数量边界（防溢出）"]
        has_rule = False
        for short_id, hold_qty in sorted(inventory_map.items()):
            item = items.get(f"item:{short_id}", {}) or items.get(short_id, {}) or {}
            effects = item.get("effects", {}) or {}
            if not effects:
                continue

            max_caps: List[int] = []
            needed_caps: List[int] = []
            effect_parts: List[str] = []

            for attr_name, raw_v in effects.items():
                v = self._safe_float(raw_v, 0.0)
                if v == 0:
                    continue
                attr_cn = ATTR_CN_MAP.get(attr_name, attr_name)
                sign = "+" if v > 0 else ""
                effect_parts.append(f"{attr_cn}{sign}{v:g}")
                if v > 0 and attr_name in attrs:
                    now_val = attrs[attr_name]
                    no_overflow = max(0, int((100.0 - now_val) // v))
                    max_caps.append(no_overflow)
                    need = max(0.0, targets.get(attr_name, now_val) - now_val)
                    need_qty = int(math.ceil(need / v)) if need > 0 else 0
                    needed_caps.append(need_qty)

            if not max_caps:
                continue

            has_rule = True
            max_no_overflow = min(hold_qty, min(max_caps))
            suggested = min(max_no_overflow, max(needed_caps) if needed_caps else 0)
            lines.append(
                f"- {short_id}：背包{hold_qty}，效果[{', '.join(effect_parts)}]；建议 consume qty={suggested}~{max_no_overflow}（超过将溢出）。"
            )

        if not has_rule:
            lines.append("- 当前背包无可用于恢复属性的物品，跳过 consume。")
        lines.append("- 规则：若建议上限为 0，禁止 consume 该物品；改为 wait/move/交易。")
        return "\n".join(lines)

    def _build_action_budget_guard(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        fatigue = self._safe_float(actor.get("fatigue"), 0.0)
        stats = self._parse_current_plan_stats(obs)
        used = int(stats["high_cost_steps"])
        budget = 1
        if fatigue >= 45:
            budget = 4
        elif fatigue >= 30:
            budget = 3
        elif fatigue >= 15:
            budget = 2
        remain = max(0, budget - used)
        last_action = stats["last_action_line"] or "无"

        lines = [
            "## 动作预算（防碎步与复读）",
            f"- 当前精神值：{fatigue:.1f}",
            f"- 本计划已执行高消耗动作：{used} 次（move/buy/sell/consume）",
            f"- 建议本回合高消耗动作预算：{budget} 次，剩余建议：{remain} 次",
            f"- 上一步动作结果：{last_action}",
            "- 规则：若已达到预算，优先 sleep（在家）或 wait（非家），不要再追加碎步交易。",
            "- 规则：与上一步动作同类型同目标/同物品时，默认判定为复读，必须换动作。",
        ]
        return "\n".join(lines)

    def _build_feasibility_guard(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        cur_loc = str(actor.get("cur_location", ""))
        at_market = cur_loc == "location:market"
        inventory_map = self._extract_inventory_map(obs)
        market_stock_map = self._extract_market_stock_map(obs)

        inv_text = "、".join(f"{k}:{v}" for k, v in sorted(inventory_map.items())) if inventory_map else "空"
        market_text = "、".join(f"{k}:{v}" for k, v in sorted(market_stock_map.items())) if market_stock_map else "空"

        lines = [
            "## 可执行性边界（高优先级）",
            f"- 当前位置：{cur_loc}",
            f"- buy/sell 是否可用：{'是' if at_market else '否（需先 move 到 location:market）'}",
            f"- 可consume物品及最大数量：{inv_text}",
            f"- 集市可买库存及最大数量：{market_text}",
            "- 规则1：若动作是 buy/sell 且你不在 location:market，下一步应优先 move 到 location:market。",
            "- 规则2：若动作是 buy/sell，qty 不能超过对应库存。",
            "- 规则3：若动作是 consume/sell，qty 不能超过背包数量。",
            "- 规则4：同一回合同一物品只能单向交易，不做买卖对冲。",
            "- 规则5：若计划下一步违反以上规则，不要试错，改为可执行的下一步。",
        ]
        return "\n".join(lines)

    def _stable_prefix_sections(self) -> List[PromptSection]:
        return [
            self._sec("## 全局约束", self.STABLE_GLOBAL_POLICY, "rules"),
            self._sec("## 输出约束", self.STABLE_OUTPUT_POLICY, "rules"),
            self._sec("## 决策协议", self.STABLE_DECISION_PROTOCOL, "rules"),
        ]

    def _build_base_sections(self, obs: Any) -> List[PromptSection]:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        day = getattr(obs, "day", -1)

        background = (
            "你受邀参加一个神秘游戏，需要在限定小镇中生存与交易。"
            "目标是尽快累计现金达到 10000元 以获胜。"
        )

        rules = "\n".join(
            [
                "- 仅依据当前提示词中的信息决策，不得补充设定。",
                "- 生存属性（饱食度/水分值/精神值）任一归零会出局。",
                "- 非必要不冒险，不做高消耗低收益动作。",
            ]
        )

        identity = f"角色：{actor.get('identity', '未知')}"
        location = f"当前位置：{actor.get('cur_location', '未知')}"
        money = f"金钱：{actor.get('money', 0):.2f}/10000元"
        attrs = (
            f"属性：饱食度 [{self._safe_float(actor.get('hunger'), 0.0):.2f}/100]，"
            f"水分值 [{self._safe_float(actor.get('thirst'), 0.0):.2f}/100]，"
            f"精神值 [{self._safe_float(actor.get('fatigue'), 0.0):.2f}/100]"
        )
        inv = f"背包：{actor.get('inventory', '空') or '空'}"
        state = "\n".join([f"日期：第{day}天", identity, location, money, attrs, inv])

        return [
            self._sec("## 背景", background, "info"),
            self._sec("## 规则", rules, "rules"),
            self._sec("## 角色状态", state, "state"),
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
        next_prices = market_loc.get("next_price", {}) or {}
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
            next_price = self._safe_float(next_prices.get(item_id), price)
            sell_ratio = self._safe_float(item.get("sell_ratio"), 0.0)
            if base_price > 0:
                ratio = price / base_price if base_price else 1.0
                if ratio >= 1.3:
                    level_text = "相比均价显著偏贵，推荐出手"
                elif ratio <= 0.7:
                    level_text = "相比均价显著偏低，推荐入手"
                elif ratio >= 1.1:
                    level_text = "相比均价略贵"
                elif ratio <= 0.9:
                    level_text = "相比均价略便宜"
                else:
                    level_text = "接近常规价格"
            else:
                level_text = "无基准价"

            if price > 0:
                drift = next_price / price
                if drift >= 1.3:
                    trend_text = "明日大涨,推荐入手"
                elif drift >= 1.1:
                    trend_text = "明日小涨"
                elif drift <= 0.7:
                    trend_text = "明日大跌，推荐出手"
                elif drift <= 0.9:
                    trend_text = "明日小跌"
                else:
                    trend_text = "明日平稳"
            else:
                trend_text = "明日趋势未知"

            lines.append(
                f"- {name}({short_id})：库存 {qty}，现价 {price:.2f}元，出售折价{sell_ratio:.2f}，{level_text}，{trend_text}；{desc}{effect_text}"
            )

        if len(lines) == 1:
            lines.append("- 当前无可交易商品")
        lines.append("出售折价说明：表示出售价格与买入价格的比例，例如 0.8 表示出售价格是买入价格的 80%。购入越有性价比的物品，出售折价越低。")

        lines.append("输出说明：item 字段请填写短 ID（如 bread、water），不要带 item: 前缀。")
        return "\n".join(lines)

    def _build_action_guide(self, obs: Any) -> str:
        actor = getattr(obs, "actor_snapshot", {}) or {}
        cur_loc = actor.get("cur_location", "")
        catalog_locations = (getattr(obs, "catalog_snapshot", {}) or {}).get("locations", {}) or {}
        move_targets = sorted(str(loc_id) for loc_id in catalog_locations.keys())
        move_targets_text = "，".join(move_targets) if move_targets else "无"

        available_actions = ["move", "consume", "sleep", "buy", "sell", "wait"]

        lines = [
            "## 动作输出要求",
            "- 只能输出一个 JSON 对象，不能输出任何额外文本。",
            f"- 允许动作类型：{', '.join(available_actions)}。",
            "- 当计划完成、无法继续或需要保守收口时，输出 {\"type\":\"wait\"}。",
            f"- 当前位置：{cur_loc}；可移动目标：{move_targets_text}。",
            "- buy/sell 仅在 location:market 执行。",
            "- consume 仅可使用背包已有物品。",
            "- 除 sleep/wait 外，动作会消耗精神值，请避免重复无效操作。",
            f"- 回合结束时，会恢复{-FATIGUE_DECAY_PER_DAY}点精神值，减少{HUNGER_DECAY_PER_DAY}点饱食度，减少{THIRST_DECAY_PER_DAY}点水分值。请注意精神值和生存属性，并斟酌使用物品，避免属性溢出(上限100)。",
            "- 不要连续输出与上一步完全相同的动作；若需要同类操作，请合并数量一次完成（例如 qty 提高）。",
            "- 当收到“上一步错误/重复动作”反馈时，下一步必须更换动作或更换参数。",
            "- 同一回合同一物品只能单向交易：若已买入该物品，本回合不要再卖出；若已卖出则不要再买入。",
            "- 禁止把同类同物品动作拆分成多次小 qty（例如连续 buy meat 1 + buy meat 1）。",
            
            "## JSON 示例",
            '{"type":"move","target":"location:market"}',
            '{"type":"consume","item":"bread","qty":1}',
            '{"type":"sleep"}',
            '{"type":"buy","item":"bread","qty":2}',
            '{"type":"sell","item":"water","qty":3}',
            '{"type":"wait"}',
        ]
        return "\n".join(lines)

    def get_top_level_plan(self, obs: Any) -> str:
        sections: List[PromptSection] = []
        sections += self._stable_prefix_sections()
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 上次反思", self.reflect_txt or "暂无", "memory"))
        sections.append(self._sec("## 地点信息", self._format_locations_info(obs), "state"))
        sections.append(self._sec("## 物价信息", self.format_market_item_list(obs), "prices_info"))

        action_space = ["前往地点", "购买/出售", "使用物品", "睡觉", "结束回合"]
        sections.append(self._sec("## 动作空间", "、".join(action_space), "action_space"))

        task = "\n".join(
            [
                "请制定本回合剩余阶段的行动计划。",
                "- 先确保生存属性安全，再追求利润。",
                f"- 除 sleep/wait 外，每次动作约消耗 {FATIGUE_DECAY_PER_ACTION} 点精神值。每回合结束时会恢复{-FATIGUE_DECAY_PER_DAY}点精神值，减少{HUNGER_DECAY_PER_DAY}点饱食度，减少{THIRST_DECAY_PER_DAY}点水分值。",
                "- 给出**至少1**条可执行步骤，按顺序编号。",
                "- 计划最多 4 步（不含“回合结束”），避免长链条件分支和碎步动作。",
                "- 计划应以策略步骤表达，不要推演执行后的具体数值，不要重写边界检查。",
                "- 同一回合同一物品只能单向交易（只买或只卖），禁止先买后卖或先卖后买。",
                "- 同一物品本回合交易步骤不超过1次；确有生存危机时最多2次。",
                "- 对 consume 步骤必须显式写“防溢出 qty 上限”，若无恢复需求就不要 consume。",
                "- 若本回合目标已完成，最后一步写“回合结束”。",
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
        current_plan_memory = getattr(obs, "memory_current_plan", "") or ""
        previous_plan_memory = getattr(obs, "memory_previous_plans", "") or ""
        sections.append(
            self._sec(
                "## 当前计划内已执行动作与结果",
                current_plan_memory or "暂无（当前计划刚开始）",
                "memory",
            )
        )
        if previous_plan_memory.strip():
            sections.append(
                self._sec(
                    "## 本回合旧计划历史（仅参考，不用于判断当前计划进度）",
                    previous_plan_memory,
                    "memory",
                )
            )
        sections.append(self._sec("## 边界检查", self._build_feasibility_guard(obs), "rules"))
        sections.append(self._sec("## 动作预算检查", self._build_action_budget_guard(obs), "rules"))
        sections.append(self._sec("## 交易方向检查", self._build_trade_direction_guard(obs), "rules"))
        sections.append(self._sec("## consume检查", self._build_consumption_guard(obs), "rules"))

        task = "\n".join(
            [
                "根据当前计划与已执行结果，输出下一步单个动作。",
                "- 优先级顺序：可执行性边界检查 > 生存安全 > 当前计划。",
                "- 只根据“当前计划内已执行动作与结果”判断当前计划进度，不要用旧计划历史对齐步骤。",
                "- 先验证下一步是否合法，再执行计划步骤。",
                "- 忽略计划中的过时数字（旧库存/旧背包/旧金额），以当前状态与边界检查为准。",
                "- 如果计划完成、计划已不适用或信息不足，输出 wait 结束回合。",
                "- 若生存属性进入危险区，允许打断计划优先自救。",
                "- 避免重复购买/重复使用同一物品造成不必要精神消耗。",
                "- buy/sell/consume 同类同物品优先一次完成（用更合适的 qty），不要拆步执行。",
                "- consume 前先按“consume检查”计算上限，qty 绝不超过上限。",
                "- 若已触发交易方向锁（某物品已买或已卖），下一步不得反向交易该物品。",
                "- 若已达到动作预算，直接 sleep 或 wait 收口，不再追加买卖/移动。",
                "- 预测“下一步”指执行计划中的下一步骤，不是复读上一动作。",
                "- 若上一动作失败或被判定重复，必须输出不同动作（或调整 target/item/qty）。",
                "- 如果出现同品买卖来回震荡，立即停止交易并输出 wait。",
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
                "请做简短反思，用于下一回合决策优化。",
                "- 仅总结已发生事实，不得虚构。",
                "- 重点写可复用策略，不要重复罗列状态数字。",
                "- 输出 3 条以内，每条一句。",
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
