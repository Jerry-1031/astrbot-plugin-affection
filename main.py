import hashlib
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
        str(
            member.get("card")
            or member.get("nickname")
            or member.get("remark")
            or fallback
        )
        if isinstance(member, dict)
        else fallback
    )


def _level_of(affection: int) -> str:
    tiers = [
        (0, 99, "朋友"),
        (100, 299, "熟人"),
        (300, 599, "心动"),
        (600, 999, "恋人"),
        (1000, 10**18, "主人"),
    ]
    for low, high, label in tiers:
        if low <= affection <= high:
            return label
    return "喵"


LUCK_INFO_SPECIAL = (
    (0, "区", "哦，你拿反了，这个不是凶，是区..."),
    (55, "半吉", "你获得了半吉中的半吉，看来今天是half吉me呢！"),
    (67, "67", "67676767"),
    (78, "大吉吉", "大吉吉！"),
)

LUCK_INFO = (
    (
        0,
        "最凶",
        (
            "要不今天咱们就在床上躲一会吧...害怕...",
            "保佑。祝你平安。",
            "哎呀，幸运值几乎触底了！整个世界都在与你作对，每一步都充满荆棘。",
            "运势黑暗至极，做任何事都如履薄冰，需万分小心。",
        ),
    ),
    (
        1,
        "大凶",
        (
            "可能有人一直盯着你......",
            "要不今天咱还是别出门了......",
            "幸运值极低，被厄运之神紧紧盯住，每一个决定都可能引发连锁的不幸。",
            "运势陷入泥潭，需要极大的毅力和勇气才能挣脱困境。",
        ),
    ),
    (
        10,
        "凶",
        (
            "啊这...昨天是不是做了什么不好的事？",
            "啊哈哈...或许需要多加小心呢。",
            "幸运值有所提升，但仍处于低谷，随时可能陷入更深的困境。",
            "运势如同过山车，时好时坏，但大部分时间都在低谷徘徊，保持警惕。",
        ),
    ),
    (
        20,
        "末吉",
        (
            "呜呜，今天运气似乎不太好...",
            "勉强能算是个吉签吧。",
            "幸运值略有波动，但整体仍不理想，仿佛被无形的障碍阻挡。",
            "迷雾中的航行，方向不明。",
        ),
    ),
    (
        30,
        "末小吉",
        (
            "唔...今天运气有点差哦。",
            "今天喝水的时候务必慢一点。",
            "幸运值有所提升，但仍处于危险边缘。",
            "暴风雨中的小船，随时可能被巨浪吞噬，需保持冷静和坚韧。",
        ),
    ),
    (
        40,
        "小吉",
        (
            "还行吧，稍差一点点呢。",
            "差不多是阴天的水平吧，不用特别担心哦。",
            "幸运值开始有所好转，但仍需小心谨慎，因为稍有不慎就可能前功尽弃。",
            "黎明前的黑暗，虽然曙光初现，但仍需耐心等待和坚持。",
        ),
    ),
    (
        50,
        "半吉",
        (
            "看样子是普通的一天呢。一切如常......",
            "加油哦！今天需要靠自己奋斗！",
            "终于摆脱了厄运，运势开始稳步上升，继续努力才能保持势头。",
            "运势如同春日里的小草，虽然刚刚探出头来，但已经充满了生机和希望。",
        ),
    ),
    (
        60,
        "吉",
        (
            "欸嘿...今天运气还不错哦？喜欢的博主或许会更新！",
            "欸嘿...今天运气还不错哦？要不去抽卡？",
            "幸运值大幅上升，幸运之神眷顾，做什么都顺风顺水。",
            "运势如同夏日里的阳光，明媚而炽热，让人感受到无尽的温暖和力量。",
        ),
    ),
    (
        70,
        "大吉",
        (
            "好耶！运气非常不错呢！今天是非常愉快的一天 ⌯>ᴗo⌯ .ᐟ.ᐟ",
            "好耶！大概是不经意间看见彩虹的程度吧？",
            "金色光环笼罩，无论做什么都能得到最好的结果。",
            "丰收的季节，硕果累累，让人感受到无尽的喜悦和满足。",
        ),
    ),
    (
        80,
        "祥吉",
        (
            "哇哦！特别好运哦！无论是喜欢的事还是不喜欢的事都能全部解决！",
            "哇哦！特别好运哦！今天可以见到心心念念的人哦！",
            "幸运几乎无人能敌，宇宙力量加持，做什么都能取得惊人的成就。",
            "璀璨的星空，每一颗星星都闪耀着耀眼的光芒，让人陶醉其中。",
        ),
    ),
    (
        90,
        "佳吉",
        (
            "૮₍ˊᗜˋ₎ა 不用多说，今天怎么度过都会顺意的！",
            "૮₍ˊᗜˋ₎ა  会发生什么好事呢？真是期待...",
            "幸运值已经接近完美，神明庇佑，做什么都能得心应手。",
            "梦幻般的仙境，每一个角落都充满了美好和奇迹。",
        ),
    ),
    (
        100,
        "最吉",
        (
            "100， 100诶！不用求人脉，好运自然来！",
            "好...好强！好事都会降临在你身边哦！",
            "哇哦！你的幸运值已经达到了宇宙的极限！仿佛被全世界的幸福和美好所包围！",
            "恭喜你成为宇宙间最幸运的人！愿你的未来永远如同神话般绚烂多彩，好运与你同在！",
        ),
    ),
    (0xFF, "No way to reach here", ("How u reach here",)),
)


@register("astrbot_mxbot", "绫濑凛", "签到、排行榜、今日老婆和今日人品", "1.1.0")
class MxBotPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = os.path.join(get_astrbot_plugin_data_path(), "astrbot_mxbot")
        self.data_file = os.path.join(self.data_dir, "state.json")
        self.state = {
            "lp_date": _today_str(),
            "groups": {},
            "jrrp": {"users": {}},
        }

    async def initialize(self):
        os.makedirs(self.data_dir, exist_ok=True)
        loaded = _load_json(self.data_file, {})
        if not loaded:
            for legacy_path in self._legacy_state_paths():
                loaded = _load_json(legacy_path, {})
                if loaded:
                    break
        if isinstance(loaded, dict):
            self.state.update(loaded)
        self._ensure_state_shape()
        self._reset_lp_if_needed()
        if loaded and not os.path.exists(self.data_file):
            _save_json(self.data_file, self.state)

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

    def _legacy_state_paths(self) -> list[str]:
        base = get_astrbot_plugin_data_path()
        return [
            os.path.join(base, "astrbot_sign_lp", "state.json"),
            os.path.join(base, "astrbot_plugin_affection", "state.json"),
        ]

    def _ensure_state_shape(self) -> None:
        self.state.setdefault("lp_date", _today_str())
        self.state.setdefault("groups", {})
        jrrp_state = self.state.setdefault("jrrp", {})
        jrrp_state.setdefault("users", {})
        for group in self.state["groups"].values():
            if not isinstance(group, dict):
                continue
            group.setdefault("sign", {})
            group.setdefault("lp", {})
            group["sign"].setdefault("users", {})
            group["lp"].setdefault("users", {})

    def _jrrp_state(self) -> dict:
        jrrp_state = self.state.setdefault("jrrp", {})
        jrrp_state.setdefault("users", {})
        return jrrp_state

    def _generate_jrrp_value(self, user_id: str, today: str) -> int:
        digest = hashlib.sha256(f"{user_id}:{today}".encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        return random.Random(seed).randint(0, 100)

    def _jrrp_level(self, luck: int) -> tuple[str, str]:
        # Special levels take precedence over normal levels
        for value, label, tip in LUCK_INFO_SPECIAL:
            if luck == value:
                return label, tip
        for low, label, tips in LUCK_INFO:
            if luck >= low:
                short_info = label
                long_info = random.choice(tips)
            else:
                break
        return short_info, long_info

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def jrrp_listener(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip().lower()
        if message.startswith(("/", "!", "！")):
            message = message.lstrip("/!！").strip()
        if message != "jrrp":
            return

        async for result in self._jrrp(event):
            yield result
        event.stop_event()

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
        return group_state["sign"]["users"].setdefault(
            user_id,
            {
                "total_days": 0,
                "continuous_days": 0,
                "affection": 0,
                "last_sign": "",
                "last_delta": 0,
                "name": "",
            },
        )

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def sign_listener(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip().lower()
        if message.startswith(("/", "!", "！")):
            message = message.lstrip("/!！").strip()
        if message not in {"签到", "qd"}:
            return

        async for result in self._sign(event):
            yield result
        event.stop_event()

    async def _sign(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只能在群里用哦。")
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
                f"已签到{record.get('total_days', 0)}天，连续签到{record.get('continuous_days', 0)}天。\n"
                f"你的好感度是{affection}（今日+{delta}），目前的等级是：{level}~"
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
            f"已签到{record['total_days']}天，连续签到{record['continuous_days']}天。\n"
            f"你的好感度是{affection}（今日+{delta}），目前的等级是：{level}~"
        )
        yield event.plain_result(text)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def sign_rank_listener(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip().lower()
        if message.startswith(("/", "!", "！")):
            message = message.lstrip("/!！").strip()
        if message not in {"签到排行榜", "排行榜", "qdphb", "phb"}:
            return

        async for result in self._sign_rank(event):
            yield result
        event.stop_event()

    async def _sign_rank(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只能在群里用哦。")
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

    async def _jrrp(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        today = _today_str()

        jrrp_state = self._jrrp_state()
        users = jrrp_state["users"]
        record = users.setdefault(
            user_id,
            {
                "date": "",
                "luck": 0,
            },
        )

        if record.get("date") != today:
            record["date"] = today
            record["luck"] = self._generate_jrrp_value(user_id, today)

        luck = int(record.get("luck", 0))
        short_info, long_info = self._jrrp_level(luck)

        message = f"你的幸运值为{luck}，判定为“{short_info}”。{long_info}"
        yield event.plain_result(message)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def today_love_listener(self, event: AstrMessageEvent):
        message = (event.message_str or "").strip().lower()
        if message.startswith(("/", "!", "！")):
            message = message.lstrip("/!！").strip()
        if message not in {"lp", "今日老婆", "jrlp"}:
            return

        async for result in self._today_love(event):
            yield result
        event.stop_event()

    async def _today_love(self, event: AstrMessageEvent):
        if event.is_private_chat():
            yield event.plain_result("这个功能只能在群里用哦。")
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
            yield event.plain_result(
                f"你今天已经有老婆{wife_name}({wife_id})了，要好好对待哦。"
            )
            return

        members = await self._fetch_group_members(event)
        candidates = members if members else []
        if not candidates:
            yield event.plain_result("拿不到群成员列表，没法抽老婆啦。")
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
            Plain(f"你的今日老婆是 {wife_name} ({wife_id})\n"),
            Image.fromURL(avatar_url),
        ]
        yield event.chain_result(chain)

    async def terminate(self):
        _save_json(self.data_file, self.state)
