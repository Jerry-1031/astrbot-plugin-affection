import json
import os
import random
from datetime import datetime, date, timedelta

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Image, Plain
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _yesterday_str() -> str:
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def _load_json(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_member_list(raw) -> list[dict]:
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], list):
        raw = raw["data"]
    return raw if isinstance(raw, list) else []


def _member_name(member: dict, fallback: str) -> str:
    return (
        str(member.get("card") or member.get("nickname") or member.get("remark") or fallback)
        if isinstance(member, dict)
        else fallback
    )


def _level_of(affection: int) -> str:
    tiers = [
        (0, 100, "朋友"),
        (101, 300, "熟人"),
        (301, 600, "心动"),
        (601, 999, "恋人"),
        (1000, 10**18, "主人"),
    ]
    for low, high, label in tiers:
        if low <= affection <= high:
            return label
    return "朋友"


@register("astrbot_sign_lp", "绫濑凛", "签到、排行榜和今日老婆", "1.0.0")
class AffectionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = os.path.join(
            get_astrbot_plugin_data_path(), "astrbot_sign_lp"
        )
        self.data_file = os.path.join(self.data_dir, "state.json")
        self.state = {
            "lp_date": _today_str(),
            "groups": {},
        }

    async def initialize(self):
        os.makedirs(self.data_dir, exist_ok=True)
        loaded = _load_json(self.data_file, self.state)
        if isinstance(loaded, dict):
            self.state.update(loaded)
        self._reset_lp_if_needed()

    async def terminate(self):
        _save_json(self.data_file, self.state)

    def _group_state(self, group_id: str) -> dict:
        groups = self.state.setdefault("groups", {})
        group = groups.setdefault(group_id, {})
        group.setdefault("sign", {})
        group.setdefault("lp", {})
        group["sign"].setdefault("users", {})
        group["lp"].setdefault("users", {})
        return group

    def _reset_lp_if_needed(self) -> None:
        today = _today_str()
        if self.state.get("lp_date") == today:
            return
        self.state["lp_date"] = today
        for group in self.state.get("groups", {}).values():
            if isinstance(group, dict) and "lp" in group:
                group.setdefault("lp", {}).setdefault("users", {})
                group["lp"]["users"] = {}

    async def _fetch_group_members(self, event: AstrMessageEvent) -> list[dict]:
        try:
            raw = await event.bot.api.call_action(
                "get_group_member_list", group_id=int(event.get_group_id())
            )
            return _normalize_member_list(raw)
        except Exception as e:
            logger.warning(f"获取群成员列表失败: {e}")
            return []

    def _current_sign_record(self, group_state: dict, user_id: str) -> dict:
        return group_state["sign"]["users"].setdefault(user_id, {
            "total_days": 0,
            "continuous_days": 0,
            "affection": 0,
            "last_sign": "",
            "last_delta": 0,
            "name": "",
        })

    @filter.command("签到")
    async def sign(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只在群里用哦。")
            return

        group_id = str(event.get_group_id())
        user_id = str(event.get_sender_id())
        sender_name = event.get_sender_name() or f"用户({user_id})"
        today = _today_str()

        group_state = self._group_state(group_id)
        record = self._current_sign_record(group_state, user_id)
        record["name"] = sender_name

        if record.get("last_sign") == today:
            delta = int(record.get("last_delta", 0))
            affection = int(record.get("affection", 0))
            level = _level_of(affection)
            text = (
                f"你今天已经签到过啦。\n"
                f"已总共签到{record.get('total_days', 0)}天，连续签到{record.get('continuous_days', 0)}天。\n"
                f"你的好感度是{affection}（今日+{delta}），目前的等级是：【{level}】~"
            )
            yield event.plain_result(text)
            return

        if record.get("last_sign") == _yesterday_str():
            continuous_days = int(record.get("continuous_days", 0)) + 1
        else:
            continuous_days = 1

        delta = random.randint(10, 20)
        affection = int(record.get("affection", 0)) + delta

        record.update(
            {
                "total_days": int(record.get("total_days", 0)) + 1,
                "continuous_days": continuous_days,
                "affection": affection,
                "last_sign": today,
                "last_delta": delta,
                "name": sender_name,
            }
        )

        level = _level_of(affection)
        text = (
            f"已总共签到{record['total_days']}天，连续签到{record['continuous_days']}天。\n"
            f"你的好感度是{affection}（今日+{delta}），目前的等级是：{level}~"
        )
        yield event.plain_result(text)

    @filter.command("签到排行榜")
    async def sign_rank(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只在群里用哦。")
            return

        group_id = str(event.get_group_id())
        group_state = self._group_state(group_id)
        users = group_state["sign"]["users"]
        if not users:
            yield event.plain_result("本群还没有签到数据呢。")
            return

        members = await self._fetch_group_members(event)
        name_map = {}
        for m in members:
            uid = str(m.get("user_id"))
            name_map[uid] = _member_name(m, uid)

        ranked = sorted(
            users.items(),
            key=lambda item: (
                int(item[1].get("affection", 0)),
                int(item[1].get("total_days", 0)),
            ),
            reverse=True,
        )[:10]

        lines = ["签到排行榜"]
        for idx, (uid, record) in enumerate(ranked, 1):
            affection = int(record.get("affection", 0))
            level = _level_of(affection)
            name = name_map.get(uid) or record.get("name") or f"用户({uid})"
            lines.append(f"{idx}. {name}({uid})  好感度{affection}  {level}")

        yield event.plain_result("\n".join(lines))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def today_love_listener(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip().lower()
        if message.startswith(("/","!","！")):
            message = message.lstrip("/!！").strip()
        if message not in {"lp", "今日老婆", "jrlp"}:
            return

        async for result in self._today_love(event):
            yield result
        event.stop_event()

    async def _today_love(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只在群里用哦。")
            return

        self._reset_lp_if_needed()

        group_id = str(event.get_group_id())
        user_id = str(event.get_sender_id())
        sender_name = event.get_sender_name() or f"用户({user_id})"
        self_id = str(event.get_self_id())

        group_state = self._group_state(group_id)
        lp_users = group_state["lp"]["users"]
        existing = lp_users.get(user_id)
        if existing:
            wife_id = str(existing.get("wife_id", ""))
            wife_name = str(existing.get("wife_name", f"用户({wife_id})"))
            if wife_id == self_id:
                yield event.plain_result("你今天已经有老婆我了！")
            else:
                yield event.plain_result(
                    f"你今天已经有老婆{wife_name}({wife_id})了！"
                )
            return

        members = await self._fetch_group_members(event)
        candidates = members if members else []
        if not candidates:
            yield event.plain_result("我拿不到群成员列表，没法抽老婆啦。")
            return

        wife = random.choice(candidates)
        wife_id = str(wife.get("user_id", ""))
        wife_name = _member_name(wife, f"用户({wife_id})")
        avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={wife_id}&spec=640"

        lp_users[user_id] = {
            "user_id": user_id,
            "user_name": sender_name,
            "wife_id": wife_id,
            "wife_name": wife_name,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        if wife_id == self_id:
            yield event.plain_result("你的今日老婆是我哦！")
            return

        chain = [
            Plain(f"你的今日老婆是 {wife_name}({wife_id})\n"),
            Image.fromURL(avatar_url),
        ]
        yield event.chain_result(chain)

    async def terminate(self):
        _save_json(self.data_file, self.state)
