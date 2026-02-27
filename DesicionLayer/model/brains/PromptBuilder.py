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
            return "，".join(f"{k} x {v}" for k, v in inventory_snapshot.items())
        return str(inventory_snapshot)

    def _build_base_sections(self, obs: Any) -> List[PromptSection]:
        # 三类 prompt 共用的背景、规则、角色状态。
        actor = getattr(obs, "actor_snapshot", {}) or {}
        day = getattr(obs, "day", -1)

        background = (
            "你受邀参加了一个神秘游戏，目标在限定的小镇场景中生存和贸易，和其它玩家博弈，你需要抢在其它玩家前赚取10000现金以获得胜利。"
        )

        rules = "\n".join(
            [
                "- 仅依据当前提示中的信息决策，不要虚构物品、地点或规则。",
                "- 优先保证生存属性（饱食度、水分值、精神值）不低于20%,任意一项属性归零将直接出局",
            ]
        )

        identity = f"角色：{actor['identity']}"
        location = f"当前位置：{actor['cur_location']}"
        money = f"金钱：{actor['money']}"
        attrs = (
            f"属性：饱食度 {round(float(actor.get('hunger', 0.0)), 2)}，"
            f"水分值 {round(float(actor.get('thirst', 0.0)), 2)}，"
            f"精神值 {round(float(actor.get('fatigue', 0.0)), 2)}"
            " 三项属性越高约安全,最高为100,每回合结束时会扣减一定比例的饥饿和口渴值，恢复一定的精神值。每次行动都会消耗5点精神值，部分特殊行为除外。"
        )
        inv = f"背包：{obs.actor_snapshot["inventory"]}"
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
        for loc_id, loc_obs in location_snapshot.items():
            loc_def = catalog_locations.get(loc_id, {})
            loc_name = loc_def.get("name", loc_id)
            loc_desc = loc_def.get("description") or loc_obs.get("desp", "")
            lines.append(f"- {loc_name} ({loc_id})：{loc_desc}")
        return "\n".join(lines) if lines else "- 暂无地点信息"


    def format_market_item_list(self, obs: Any) -> str:
        title = "### 市场商品"
        location_snapshot = obs.location_snapshot
        market = location_snapshot["location:market"]["market"]
        stock = market["stock"]
        cur_price = market["price"]
        next_prices = market["next_price"]
        items = obs.catalog_snapshot["items"]

        lines: List[str] = [title]
        for item_id, qty in stock.items():
            if qty is None or int(qty) <= 0:
                continue
            item = items.get(item_id, {})
            name = item.get("name", item_id)
            desc = item.get("description", "")
            effects = []
            for name,value in item["effects"].items():
                if isinstance(value, str):
                    effects += f"{value}"
                    continue
                if value == 0:
                    continue
                elif value <0:
                    effects.append(f"{name}-{abs(value)}")
                elif value >0:
                    effects.append(f"{name}+{value}")
            desc +="功能："+ ",".join(effects)
            base_price = item['base_price']
            price = cur_price[item_id]
            next_price = next_prices[item_id]
            if base_price > 0:
                ratio = price / base_price
                if ratio >= 1.3:
                    price_info = "相比市场均价显著偏贵,非生存所需不建议入手，"
                elif ratio <= 0.7:
                    price_info = "相比市场均价显著偏低，适合理财"
                else:
                    price_info = "接近常规价格"
            ratio = next_price / price
            price_info += "，明日价格将"
            if ratio >= 1.1:
                price_info += "小涨"
            elif ratio <= 0.9:
                price_info += "小跌"
            elif ratio >= 1.3:
                price_info += "大涨"
            elif ratio <= 0.7:
                price_info += "大跌"
            else:
                price_info += "平稳"
            
            lines.append(
                f"- {name}({item_id}) , 库存 {qty} , 价格 {price:.2f} , {price_info} , {desc}"
            )
        if len(lines) == 1:
            lines.append("- 当前无可交易商品")
        lines.append("集市目前只包含以上商品，商品先到先得，可能已经被买走了，商品种类会随着回合升高而增多。")
        lines.append(r"明日价格涨跌幅大于10%s视为小涨和小跌，大于30%s视为大涨和大跌")
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
            "- 只输出 JSON 对象,仅包含一个有效动作，不要输出额外文本。",
            f"- 允许动作类型：{', '.join(available_actions)}。",
            "- 计划完成时输出 {\"type\":\"finish\"}。",
            f"- 当前位置：{cur_loc}；可移动目标：{move_targets_text}。",
            "- buy/sell; 仅在市场地点执行，item 必须来自市场商品列表。",
            "- consume 仅可使用背包已有物品。",
            "## 示例",
            '{"type":"move","target":"location:market"},前往某个地点',
            '{"type":"consume","item":"bread","qty":1},消耗物品，触发物品功能',
            '{"type":"sleep"},睡觉，消耗水分和饱食度回复精神(恢复20点，扣减8点饥饿,扣减10点水分),该动作不会额外消耗精神',
            '{"type":"buy","item":"bread","qty":2},购买物品',
            '{"type":"sell","item":"apple","qty":5},出售物品',
            '{"type":"wait"},结束回合并等待，此动作不消耗精神值'
            '{"type":"finish"},完成了当前计划，等待下一次计划，此动作不消耗精神值',
        ]
        
        return "\n".join(lines)

    def get_top_level_plan(self, obs: Any) -> str:
        # 中期计划：给模型一个“接下来几小时”目标框架。
        sections: List[PromptSection] = []
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 上次反思", self.reflect_txt or "暂无", "memory"))
        sections.append(self._sec("## 地点信息", self._format_locations_info(obs), "state"))
        sections.append(self._sec("## 物价信息(以下是全部商品信息，前往集市以购买)", self.format_market_item_list(obs), "prices_info"))
        action_space = ["前往某地","购买或出售物品","睡觉","使用背包中的物品"]
        sections.append(self._sec("## 动作空间","、".join(action_space), "action_space"))
        task = "\n".join(
            [ 
                "请指定本回合的剩余时间的计划，如果已经达成所有目标，则计划最后一步输出“回合结束”。",
                "- 优先保障生存，然后考虑获利方案",
                "- 执行动作空间内的任何动作都会消耗5点精神值，你可以通过购买商店中的物品并在背包中使用以回复水分值和饱食度，睡觉以回复20精神值。",
                "- 输出简洁，只包含至少1条计划,不用给出理由、预测、情况复盘",
                "- 最好可以给出具体数值结果（非强制）"
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
        if cur_loc == "location:market":
            location_info = f"{location_info}\n\n{self.format_market_item_list(obs)}"
        sections.append(self._sec("## 当前地点信息", location_info, "state"))


    
        sections.append(self._sec("## 本回合已经执行的动作和结果", obs.memory or "", "memory"))

        sections.append(self._sec("## 当前计划", self.plan_txt or "暂无", "memory"))

        task = "\n".join(
            [
                "- 请基于严格按照当前计划，并结合本回合已经执行的动作推测计划执行到了哪一步，然后输出下一步计划，少量的数值差异请忽略，以具体步骤为准",
                "- 根据当前计划预测下一个动作不是指找规律，而是根据计划执行下一个动作"
                "- 若计划完成，输出 `finish`,如果计划的最后明确提到**回合结束**，而且计划中的步骤已经基本完成了，则输出 `wait`，表示结束回合",
                "- 如果当前某一项属性陷入危险区域，优先考虑恢复属性，可强行打破计划或直接输出 `finish`"
                "- 输出睡觉(sleep)以外的任何动作都会消耗2精神值，购买、使用物品等动作建议一次完成，不要反复购买或使用同一个物品，这会带来不必要的精神值消耗。"
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
        # 反思提示词：把近期事件压缩成可复用经验文本。
        sections: List[PromptSection] = []
        sections += self._build_base_sections(obs)
        sections.append(self._sec("## 本回合已执行动作和结果",obs.memory or "", "memory"))
        sections.append(self._sec("## 最近计划", self.plan_txt , "memory"))

        task = "\n".join(
            [
                "请基于本回合已执行的动作和结果做简短总结与反思，目的是能够做好下一回合的计划",
                "- 只总结已发生的事，不要虚构",
                "- 尽量避免复述人物状态，比如“背包空，饱食度为50”等无效描述"
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
