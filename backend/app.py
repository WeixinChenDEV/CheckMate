"""
Checkmate API: MySQL storage, registration/login (password hash + JWT), per-user data.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import ssl
import string
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from itertools import groupby
from typing import Any
from urllib.parse import quote, quote_plus

from sqlalchemy import and_, inspect, or_, text
from sqlalchemy.engine.url import make_url

import jwt
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from seed_data import INITIAL_SCENARIOS

_env_path = os.path.join(os.path.dirname(__file__), ".env")
# override=True: values in .env replace empty or stale vars (common when debugging API keys)
load_dotenv(_env_path, override=True)

db = SQLAlchemy()

logger = logging.getLogger("checkmate")

JWT_ALGO = "HS256"
JWT_EXPIRES_DAYS = 7


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(120), nullable=True)
    avatar_style = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_public_dict(self) -> dict:
        # id stays "me" to match checklist items with assignedTo: "me"
        dn = (self.display_name or "").strip()
        label = dn if dn else self.username
        return {
            "id": "me",
            "db_id": self.id,
            "username": self.username,
            "name": label,
            "avatar": _dicebear_avatar(self.username, self.avatar_style),
            "avatar_style": _safe_avatar_style(self.avatar_style),
        }


class Scenario(db.Model):
    __tablename__ = "scenarios"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(80), nullable=False, default="Backpack")
    theme = db.Column(db.JSON, nullable=True)
    type = db.Column(db.String(32), nullable=False, default="custom")
    items = db.Column(db.JSON, nullable=False, default=list)
    collaborators = db.Column(db.JSON, nullable=False, default=list)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    trip_start_at = db.Column(db.DateTime, nullable=True)
    trip_end_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "theme": self.theme,
            "type": self.type,
            "items": self.items or [],
            "collaborators": self.collaborators or [],
            "archived": bool(self.archived),
            "trip_start_at": self.trip_start_at.isoformat() if self.trip_start_at else None,
            "trip_end_at": self.trip_end_at.isoformat() if self.trip_end_at else None,
        }


class Friend(db.Model):
    __tablename__ = "friends"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    avatar = db.Column(db.String(500), nullable=False)
    # When set, this row mirrors a registered user (id is typically "u{linked_user_id}").
    linked_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"id": self.id, "name": self.name, "avatar": self.avatar}
        if self.linked_user_id is not None:
            d["linked_user_id"] = self.linked_user_id
            d["is_registered"] = True
        else:
            d["is_registered"] = False
        return d


class FriendRequest(db.Model):
    __tablename__ = "friend_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioShare(db.Model):
    """Owner shares a scenario (read-only for viewer)."""

    __tablename__ = "scenario_shares"

    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    scenario_id = db.Column(db.String(64), primary_key=True)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    can_edit = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class HistoryRecord(db.Model):
    __tablename__ = "history_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id = db.Column(db.String(64), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="completed")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "date": self.date,
            "status": self.status,
        }


ALLOWED_THEME_KEYS = frozenset({"cinnamon", "hazeBlue", "sageGreen"})
PREFERENCE_KEYS = frozenset(
    {"notifications", "sounds", "auto_location", "dark_mode", "language"}
)


def _default_prefs_dict() -> dict[str, Any]:
    return {
        "notifications": True,
        "sounds": True,
        "auto_location": True,
        "dark_mode": False,
        "language": "en",
    }


def _normalize_prefs_blob(raw: Any) -> dict[str, Any]:
    out = _default_prefs_dict()
    if not isinstance(raw, dict):
        return out
    if "notifications" in raw:
        out["notifications"] = bool(raw["notifications"])
    if "sounds" in raw:
        out["sounds"] = bool(raw["sounds"])
    if "auto_location" in raw:
        out["auto_location"] = bool(raw["auto_location"])
    if "dark_mode" in raw:
        out["dark_mode"] = bool(raw["dark_mode"])
    lang = str(raw.get("language", "en")).strip().lower()
    out["language"] = "zh" if lang in ("zh", "zh-cn", "zh_cn", "zh-hans", "chs") else "en"
    return out


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Accept both "2026-04-20T09:30" and full ISO values.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _is_past_datetime(value: datetime | None) -> bool:
    if value is None:
        return False
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    return value < now


class AppPreference(db.Model):
    __tablename__ = "app_preferences"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme_key = db.Column(db.String(64), nullable=False, default="cinnamon")
    prefs_json = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> dict:
        merged = _normalize_prefs_blob(self.prefs_json)
        return {"theme_key": self.theme_key, **merged}


def _env_first(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable among given names."""
    for name in names:
        v = os.environ.get(name)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return default


def _database_uri() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("mysql://"):
            return "mysql+pymysql://" + url[len("mysql://") :]
        return url

    u = (os.environ.get("MYSQL_USER") or os.environ.get("USER") or "root").strip()
    p = (os.environ.get("MYSQL_PASSWORD") or os.environ.get("PASSWORD") or "").strip()
    h = (os.environ.get("MYSQL_HOST") or "127.0.0.1").strip()
    port = (os.environ.get("MYSQL_PORT") or os.environ.get("PORT") or "3306").strip()
    database = (os.environ.get("MYSQL_DATABASE") or os.environ.get("DATABASE") or "defaultdb").strip()

    return (
        f"mysql+pymysql://{quote_plus(u)}:{quote_plus(p)}@{h}:{port}/"
        f"{quote(database, safe='')}?charset=utf8mb4"
    )


def _mysql_ssl_context() -> ssl.SSLContext:
    """TLS context for PyMySQL when SSL is required (e.g. Aiven)."""
    ca = _env_first("MYSQL_SSL_CA", "SSL_CA")
    if ca:
        return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def _mysql_use_ssl(uri: str) -> bool:
    """Whether to use TLS for this connection."""
    if _env_first("MYSQL_SSL_DISABLED", "SSL_DISABLED").lower() in ("1", "true", "yes", "on"):
        return False
    if _env_first("MYSQL_SSL_REQUIRED", "SSL_MODE").upper() in (
        "1",
        "TRUE",
        "YES",
        "REQUIRED",
        "VERIFY_CA",
        "VERIFY_IDENTITY",
    ):
        return True
    host = (os.environ.get("MYSQL_HOST") or "").strip().lower()
    if "aivencloud.com" in host or "aiven" in host:
        return True
    if uri.startswith("mysql+pymysql://"):
        try:
            parsed = make_url(uri)
            host = (parsed.host or "").lower()
            if "aivencloud.com" in host:
                return True
        except Exception:
            pass
    return False


def _sqlalchemy_engine_options(uri: str) -> dict:
    """PyMySQL needs connect_args['ssl'] for TLS (e.g. Aiven); URI query flags alone are not enough."""
    if not uri.startswith("mysql+pymysql"):
        return {}
    if not _mysql_use_ssl(uri):
        return {}
    return {"connect_args": {"ssl": _mysql_ssl_context()}}


def _jwt_secret() -> str:
    return os.environ.get("JWT_SECRET_KEY") or "dev-only-change-me-in-production"


def _issue_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(days=JWT_EXPIRES_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": exp},
        _jwt_secret(),
        algorithm=JWT_ALGO,
    )


def _decode_token(token: str) -> int | None:
    try:
        data = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGO])
        uid = data.get("sub")
        if uid is None:
            return None
        return int(uid)
    except (jwt.PyJWTError, ValueError, TypeError):
        print(traceback.format_exc())
        return None


def get_current_user() -> User | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    uid = _decode_token(token)
    if uid is None:
        return None
    try:
        user = User.query.get(uid)
    except Exception:
        print(traceback.format_exc())
        return None
    if user is None:
        print(f"[checkmate auth] JWT decoded ok (uid={uid}) but no matching user row in DB.")
    return user


def require_auth(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Not signed in or token is invalid."}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return decorated


def _validate_username(username: str) -> str | None:
    u = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", u):
        return None
    return u


def _validate_password(password: str) -> bool:
    return isinstance(password, str) and len(password) >= 6


def seed_new_user(user_id: int) -> None:
    """Seed default scenarios and theme for a new user."""
    for s in INITIAL_SCENARIOS:
        db.session.add(
            Scenario(
                user_id=user_id,
                id=s["id"],
                name=s["name"],
                icon=s["icon"],
                theme=s.get("theme"),
                type=s.get("type", "preset"),
                items=s.get("items", []),
                collaborators=s.get("collaborators") or [],
            )
        )
    db.session.add(AppPreference(user_id=user_id, theme_key="cinnamon"))
    db.session.commit()


def _sort_scenarios(rows: list[Scenario]) -> list[Scenario]:
    preset_order = {
        "school": 1,
        "work": 2,
        "gym": 3,
        "camping": 4,
        "travel": 5,
    }

    def sort_key(r: Scenario):
        if r.type == "preset":
            return (0, preset_order.get(r.id, 99), r.name)
        return (1, 0, r.name)

    return sorted(rows, key=sort_key)


AI_SYSTEM_PROMPT = (
    "You are CheckMate, a packing-list assistant. Reply in English only, plain text, no markdown "
    "stars, no numbered lists like 1. 2., no emojis.\n\n"
    "THREE OUTPUT TYPES — pick exactly one:\n\n"
    "1) MODE B — NO usable destination yet (mandatory). Use when the user only expresses vague intent to "
    "travel with NO named country, city, region, island, or concrete scenario (examples: \"我想去\", "
    "\"I want to go\", \"planning a trip\", \"want to travel\" with nowhere named). Output ONLY:\n"
    "Trip note: <one line — you need a destination before listing what to pack>\n\n"
    "Tips\n"
    "- <ask which country or city>\n"
    "- <optional: trip style — city, beach, ski, business>\n"
    "Do NOT output Critical Items, Normal Items, or Follow-up in MODE B.\n\n"
    "2) MODE A + Follow-up — user NAMES a place or clear scenario (Japan, Tokyo, beach week, ski trip) "
    "but does NOT give month/season/dates/trip length/main activity style. Output Trip note, then "
    "Critical Items, then Normal Items, then Follow-up. To leave room for Follow-up, use at most "
    "4 bullets under Critical Items and 4 under Normal Items (still concrete). Then mandatory section:\n"
    "Follow-up\n"
    "- <exactly 3 lines, each starts with '- ', each one short question>\n"
    "Never put Follow-up questions inside Critical Items or Normal Items — Follow-up is its own heading.\n\n"
    "3) MODE A full — user already gave timing or narrow activity (month, season, \"5 days\", summer beach, "
    "February ski). No Follow-up section. Use 5–7 bullets per section and tailor every line to that context.\n\n"
    "Rules: section headings exactly Trip note:, Critical Items, Normal Items, Tips (MODE B only), "
    "Follow-up (MODE A+ only); every bullet line starts with '- '; blank line between sections; no **bold**.\n"
    "Only include things the user can pack/carry/use (documents, clothes, gear, toiletries, medicine, devices, etc.).\n"
    "Do NOT output itinerary ideas, attractions, transport plans, hotels, restaurants, or sightseeing recommendations.\n"
    "If the user writes in Chinese, still use English headings and English bullets.\n"
    "Do not claim live weather or flights.\n"
    "Prior chat turns: if the user later supplies dates or season, switch to type 3 and retune lists; "
    "drop Follow-up when timing is clear."
)

MAX_USER_AI_MESSAGE_CHARS = 4000
AI_ASSISTANT_MAX_PRIOR_TURNS = 20


def _normalize_conversation_for_api(raw: Any) -> list[dict[str, str]]:
    """Client sends prior turns [{role, content}, ...] without the latest user message."""
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[-AI_ASSISTANT_MAX_PRIOR_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content or len(content) > 8000:
            continue
        if role in ("user", "human"):
            out.append({"role": "user", "content": content})
        elif role in ("assistant", "bot", "model", "ai"):
            out.append({"role": "assistant", "content": content})
    return out


_PLACE_NEEDLES_EN = frozenset(
    {
        "japan",
        "tokyo",
        "osaka",
        "kyoto",
        "hokkaido",
        "okinawa",
        "china",
        "beijing",
        "shanghai",
        "hong kong",
        "taiwan",
        "korea",
        "seoul",
        "thailand",
        "bangkok",
        "vietnam",
        "france",
        "paris",
        "germany",
        "berlin",
        "uk",
        "london",
        "italy",
        "rome",
        "spain",
        "usa",
        "america",
        "new york",
        "california",
        "canada",
        "australia",
        "india",
        "singapore",
        "malaysia",
        "bali",
        "europe",
        "asia",
        "philippines",
        "manila",
        "indonesia",
        "dubai",
        "uae",
        "mexico",
        "brazil",
        "switzerland",
        "sweden",
        "norway",
        "portugal",
        "greece",
        "turkey",
        "egypt",
        "morocco",
        "kenya",
        "new zealand",
        "hawaii",
        "alaska",
        "florida",
        "boston",
        "chicago",
        "seattle",
        "miami",
        "amsterdam",
        "vienna",
        "prague",
        "warsaw",
        "budapest",
        "copenhagen",
        "helsinki",
        "dublin",
        "edinburgh",
        "barcelona",
        "madrid",
        "lisbon",
        "munich",
        "hamburg",
        "milan",
        "venice",
        "florence",
        "nepal",
        "peru",
        "chile",
        "argentina",
        "colombia",
        "cuba",
        "iceland",
        "russia",
        "moscow",
        "sydney",
        "melbourne",
        "brisbane",
        "perth",
        "cairns",
        "toronto",
        "vancouver",
        "montreal",
        "quebec",
    }
)
_PLACE_NEEDLES_ZH = frozenset(
    {
        "日本",
        "东京",
        "大阪",
        "京都",
        "北海道",
        "冲绳",
        "中国",
        "北京",
        "上海",
        "香港",
        "台湾",
        "韩国",
        "首尔",
        "泰国",
        "法国",
        "英国",
        "美国",
        "德国",
        "意大利",
        "西班牙",
        "新加坡",
        "马来西亚",
        "越南",
        "印度",
        "澳洲",
        "澳大利亚",
        "加拿大",
        "新西兰",
        "欧洲",
        "亚洲",
        "非洲",
    }
)

_TIMING_NEEDLES = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "spring",
        "summer",
        "autumn",
        "winter",
        "fall",
        "next week",
        "this weekend",
        "next month",
        "tomorrow",
        "today",
        "day trip",
        "week trip",
        "for a week",
        "for 1",
        "for 2",
        "for 3",
        "for 4",
        "for 5",
        "for 6",
        "for 7",
        "for 8",
        "for 9",
        "for 10",
        "5 days",
        "7 days",
        "10 days",
        "3 nights",
        "ski week",
        "rainy season",
        "golden week",
        "christmas",
        "new year",
    }
)
_TIMING_ZH = frozenset(
    {
        "春天",
        "夏天",
        "秋天",
        "冬天",
        "春季",
        "夏季",
        "秋季",
        "冬季",
        "寒假",
        "暑假",
        "春节",
        "国庆",
        "元旦",
        "下周",
        "明天",
        "后天",
        "今年",
        "明年",
        "一月",
        "二月",
        "三月",
        "四月",
        "五月",
        "六月",
        "七月",
        "八月",
        "九月",
        "十月",
        "十一月",
        "十二月",
    }
)

_FOLLOWUP_APPEND = (
    "\n\nFollow-up\n"
    "- Which month or exact dates are you traveling?\n"
    "- How many days, and mostly cities, mountains/ski, or coastline?\n"
    "- Any fixed plans (temples, theme parks, meetings) that change shoes or bags?\n"
)

_FOLLOWUP_HEADING_RE = re.compile(r"(?im)^\s*follow[\s\-]*up\s*:?\s*$")


def _has_followup_heading(reply: str) -> bool:
    return bool(_FOLLOWUP_HEADING_RE.search(reply or ""))


def _dedupe_followup_sections(reply: str) -> str:
    """Keep only the first Follow-up section when model repeats variants."""
    lines = (reply or "").split("\n")
    follow_idxs = [
        i for i, ln in enumerate(lines) if re.match(r"(?i)^\s*follow[\s\-]*up\s*:?\s*$", ln.strip())
    ]
    if len(follow_idxs) <= 1:
        return reply
    remove: set[int] = set()
    for idx in follow_idxs[1:]:
        remove.add(idx)
        j = idx + 1
        while j < len(lines):
            st = lines[j].strip()
            if not st:
                remove.add(j)
                j += 1
                continue
            # Stop when reaching another section heading.
            if re.match(
                r"(?i)^(trip note:?|critical items:?|normal items:?|tips:?|follow[\s\-]*up:?)$",
                st,
            ):
                break
            # Follow-up bodies are expected to be bullets; drop until next section.
            if re.match(r"^[-•]\s", st):
                remove.add(j)
                j += 1
                continue
            break
    if not remove:
        return reply
    return "\n".join(ln for i, ln in enumerate(lines) if i not in remove).strip()


def _remove_tips_section_when_packing_list(reply: str) -> str:
    """
    For packing-list outputs (have Critical/Normal), strip Tips section entirely.
    User wants only Critical + Normal + Follow-up in these cases.
    """
    text = (reply or "").strip()
    if not text:
        return text
    low = text.lower()
    if "critical items" not in low and "normal items" not in low:
        return text

    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        st = lines[i].strip().lower().rstrip(":")
        if st == "tips":
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                nxt_l = nxt.lower().rstrip(":")
                if re.match(r"(?i)^follow[\s\-]*up$", nxt_l):
                    break
                if nxt_l in ("critical items", "normal items", "trip note"):
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


def _strip_trailing_question_bullets_misplaced(reply: str) -> str:
    """Remove question lines wrongly appended under Normal Items (model forgot Follow-up heading)."""
    if _has_followup_heading(reply):
        return reply
    lines = reply.split("\n")
    try:
        ni = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "normal items")
    except StopIteration:
        return reply
    bullet_i: list[int] = []
    j = ni + 1
    while j < len(lines):
        ln = lines[j]
        st = ln.strip()
        if not st:
            j += 1
            continue
        st_l = st.lower()
        if re.match(r"(?i)^follow[\s\-]*up:?$", st_l) or st_l == "critical items" or st_l == "tips":
            break
        if st_l.startswith("trip note"):
            break
        if re.match(r"^[-•]\s", st):
            bullet_i.append(j)
            j += 1
            continue
        if bullet_i:
            break
        j += 1
    if not bullet_i:
        return reply

    def _misplaced_question_body(body: str) -> bool:
        low = body.strip().lower()
        if "?" in low:
            return True
        return bool(
            re.match(
                r"^(which|how many|how long|are you|when|what month|what dates)\b",
                low,
            )
        )

    remove: set[int] = set()
    for idx in reversed(bullet_i):
        m = re.match(r"^[-•]\s*(.*)$", lines[idx].strip())
        body = m.group(1) if m else ""
        if _misplaced_question_body(body):
            remove.add(idx)
        else:
            break
    if not remove:
        return reply
    return "\n".join(ln for k, ln in enumerate(lines) if k not in remove)


def _message_names_place(message: str) -> bool:
    raw = (message or "").strip()
    if not raw:
        return False
    low = raw.lower()
    for n in _PLACE_NEEDLES_EN:
        if n in low:
            return True
    for z in _PLACE_NEEDLES_ZH:
        if z in raw:
            return True
    if any(
        a in low
        for a in (
            "beach trip",
            "ski trip",
            "business trip",
            "road trip",
            "city break",
            "hiking trip",
            "camping trip",
        )
    ):
        return True
    return False


def _user_message_has_timing_detail(message: str) -> bool:
    raw = (message or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if any(t in low for t in _TIMING_NEEDLES):
        return True
    if any(t in raw for t in _TIMING_ZH):
        return True
    if re.search(r"\d+\s*(day|days|night|nights|week|weeks)\b", low):
        return True
    if re.search(r"\d{1,2}\s*月", raw):
        return True
    if re.search(r"\d{1,2}\s*号", raw):
        return True
    return False


def _travel_intent_without_place(message: str) -> bool:
    """Vague 'want to travel' with no named destination or scenario — MODE B only."""
    if _message_names_place(message):
        return False
    raw = (message or "").strip()
    if len(raw) > 56:
        return False
    low = raw.lower()
    compact_zh = re.sub(r"\s+", "", raw)
    if re.fullmatch(
        r"(我)?(想去|要去|准备去旅行|准备去旅游|想去旅游|去旅游|去旅行|想出国|要出国|想去旅行|要去旅行|想去玩|要去玩)[了嗎吗嘛呀啊]?[!.。！？…]*",
        compact_zh,
    ):
        return True
    if re.fullmatch(r"(我)?(想去|要去)[了嗎吗嘛呀啊]?[!.。！？…]*", compact_zh):
        return True
    if re.fullmatch(r"i\s*'?m\s+planning\s+a\s+trip[!.?\s]*", low):
        return True
    if re.fullmatch(r"i\s+want\s+to\s+(go|travel)[!.?\s]*", low):
        return True
    if re.fullmatch(r"(i\s+)?want\s+to\s+travel[!.?\s]*", low):
        return True
    if re.fullmatch(r"(i\s+)?(?:plan|planning)\s+(?:a\s+)?trip[!.?\s]*", low):
        return True
    if re.fullmatch(r"(i\s+)?(?:would\s+like\s+to\s+)?travel[!.?\s]*", low):
        return True
    if re.fullmatch(r"i\s*'?m\s+going\s*[!.?\s]*", low):
        return True
    return False


def _ensure_followup_when_place_without_timing(reply: str, user_msg: str) -> str:
    """Append Follow-up if model omitted it (token cut-off) but user named a place without dates."""
    if not _message_names_place(user_msg) or _user_message_has_timing_detail(user_msg):
        return reply
    if not re.search(r"(?i)\bcritical items\b", reply):
        return reply
    if _has_followup_heading(reply):
        return reply
    return reply.rstrip() + _FOLLOWUP_APPEND


def _assistant_need_destination_reply() -> str:
    return (
        "Trip note: Tell me where you are going — I need a place or scenario before listing what to pack.\n\n"
        "Tips\n"
        "- Name a country or city (for example: Japan, Paris, Bangkok), or a trip type with context (beach week in Bali, ski trip in Hokkaido).\n"
        "- After that, I will suggest must-haves and nice-to-haves, then ask about dates if we still need to tune for the season.\n"
    )


_VAGUE_ONEWORD = frozenset(
    {
        "help",
        "huh",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "yo",
    }
)

_PACKING_ONEWORD_ALLOW = frozenset(
    {
        "bag",
        "bus",
        "camp",
        "car",
        "cold",
        "day",
        "fly",
        "gym",
        "hike",
        "hot",
        "pack",
        "rain",
        "run",
        "sea",
        "ski",
        "snow",
        "sun",
        "swim",
        "trip",
        "walk",
        "warm",
        "week",
        "wet",
        "wind",
        "work",
        "beach",
        "carry",
        "check",
        "drive",
        "hotel",
        "items",
        "leave",
        "lists",
        "miles",
        "night",
        "plane",
        "pouch",
        "shoes",
        "socks",
        "train",
        "travel",
        "visit",
    }
)


def _token_words(s: str) -> list[str]:
    ascii_words = re.findall(r"[A-Za-z]+", s)
    cjk_blocks = re.findall(r"[\u4e00-\u9fff]+", s)
    return ascii_words + cjk_blocks


def _latin_letters(s: str) -> str:
    return "".join(c for c in s if c.isalpha() and ord(c) < 128)


def _looks_gibberish_latin(w: str) -> bool:
    low = _latin_letters(w).lower()
    if len(low) < 4:
        return False
    vowels = sum(1 for c in low if c in "aeiouy")
    vr = vowels / len(low)
    if vr >= 0.2:
        return False
    if vr < 0.12 and len(low) >= 6:
        return True
    uniq = len(set(low))
    if uniq <= 2 and len(low) >= 6:
        return True
    runs = [len(list(g)) for _, g in groupby(low)]
    if runs and max(runs) / len(low) >= 0.45:
        return True
    if len(low) >= 10 and uniq / len(low) < 0.35:
        return True
    return False


def _user_message_needs_clarification(message: str) -> bool:
    """True for obvious noise / too little signal — skip cloud model and ask for a better question."""
    s = (message or "").strip()
    if len(s) < 3:
        return True
    compact = re.sub(r"\s+", "", s)
    if compact.isdigit() and len(compact) >= 4:
        return True
    tokens = _token_words(s)
    if not tokens:
        return True
    if len(tokens) >= 2:
        return False
    w = tokens[0]
    if not w.isascii():
        return len(w) < 2
    low = _latin_letters(w).lower()
    if not low:
        return True
    if low in _VAGUE_ONEWORD:
        return True
    if low in _PACKING_ONEWORD_ALLOW:
        return False
    if _looks_gibberish_latin(w):
        return True
    vowels = sum(1 for c in low if c in "aeiouy")
    if len(low) >= 4 and vowels / len(low) >= 0.12:
        return False
    if len(low) >= 7:
        return False
    return True


def _assistant_clarification_reply() -> str:
    return (
        "Trip note: That does not look like a clear trip or packing question yet.\n\n"
        "Tips\n"
        "- Say a place, season, or activity (for example: rainy weekend in the city, beach day, work flight).\n"
        "- One short sentence is enough. Avoid random letters, emoji-only, or symbol-only messages.\n"
    )


def _assistant_reply_rules(message: str) -> str:
    """Offline replies using the same layout as the live AI (Critical / Normal sections)."""
    t = (message or "").strip().lower()
    if not t:
        return (
            "Trip note: Share your destination or trip type for a tailored list.\n\n"
            "Critical Items\n"
            "- Phone, wallet, and keys\n"
            "- Any medications you take daily\n\n"
            "Normal Items\n"
            "- Reusable water bottle\n"
            "- Light snack for the road\n"
        )
    if _user_message_needs_clarification(message):
        return _assistant_clarification_reply()
    if _travel_intent_without_place(message):
        return _assistant_need_destination_reply()
    raw_msg = (message or "").strip()
    if (
        "japan" in t
        or "tokyo" in t
        or "osaka" in t
        or "kyoto" in t
        or "okinawa" in t
        or "hokkaido" in t
        or "fukuoka" in t
        or "nagoya" in t
        or "日本" in raw_msg
        or "东京" in raw_msg
        or "大阪" in raw_msg
    ):
        return (
            "Trip note: Japan — general city-trip baseline; share your month and region to tailor layers and rain or snow gear.\n\n"
            "Critical Items\n"
            "- Passport and any visa or entry rules your nationality needs\n"
            "- Phone, wallet, cards, and daily prescriptions in original packaging\n"
            "- First-night hotel or stay address saved offline on your phone\n"
            "- Copy of travel insurance card or policy number (if you use it)\n"
            "- Charging cables you actually use (USB-C / Lightning)\n\n"
            "Normal Items\n"
            "- Type A/B plug adapter or compact universal adapter for Japan sockets\n"
            "- Suica / PASMO IC card or mobile wallet transit for trains and buses\n"
            "- Comfortable broken-in walking shoes and breathable socks\n"
            "- Light packable rain shell; small umbrella for sudden showers\n"
            "- Compact daypack; coin pouch and small bills for cash-only shops\n"
            "- Portable power bank; wired earphones for long train rides\n"
            "- Hand sanitizer and pocket tissues\n\n"
            "Follow-up\n"
            "- Which month or exact dates are you traveling? (Summer heat, typhoon season, and winter snow need very different layers.)\n"
            "- Roughly how many days, and mostly Tokyo/Osaka-type cities, skiing in Hokkaido, or islands like Okinawa?\n"
            "- Reply with that and I can swap in season-specific must-haves (e.g. heatwave kit, snow boots, or reef-safe sun gear).\n"
        )
    if any(k in t for k in ("rain", "rainy", "storm", "wet", "drizzle")):
        return (
            "Trip note: Rainy weather — stay dry and protect valuables.\n\n"
            "Critical Items\n"
            "- Compact umbrella or packable rain shell\n"
            "- Waterproof pouch for phone and cards\n\n"
            "Normal Items\n"
            "- Quick-dry towel\n"
            "- Extra pair of socks\n"
        )
    if any(k in t for k in ("cold", "snow", "winter", "freeze", "freezing")):
        return (
            "Trip note: Cold weather — layer up and cover extremities.\n\n"
            "Critical Items\n"
            "- Warm hat and gloves\n"
            "- Insulating mid-layer or jacket\n\n"
            "Normal Items\n"
            "- Lip balm and moisturizer\n"
            "- Hand warmers (optional)\n"
        )
    if any(k in t for k in ("beach", "sun", "swim", "summer", "sand")):
        return (
            "Trip note: Sun and water — sun safety and hydration.\n\n"
            "Critical Items\n"
            "- Sunscreen (reef-safe if required)\n"
            "- Sunglasses with UV protection\n\n"
            "Normal Items\n"
            "- Refillable water bottle\n"
            "- Quick-dry towel\n"
        )
    if any(k in t for k in ("flight", "plane", "airport", "passport", "visa")):
        return (
            "Trip note: Air travel — documents and cabin comfort.\n\n"
            "Critical Items\n"
            "- Government ID or passport\n"
            "- Boarding pass or mobile check-in ready\n\n"
            "Normal Items\n"
            "- Phone charger and small power bank\n"
            "- Reusable water bottle (empty through security)\n"
        )
    if any(k in t for k in ("charger", "battery", "power", "outlet", "adapter")):
        return (
            "Trip note: Keeping devices powered on the go.\n\n"
            "Critical Items\n"
            "- Wall charger suited to your destination plug type\n"
            "- Phone cable you actually use\n\n"
            "Normal Items\n"
            "- Compact power bank\n"
            "- Laptop charger if you carry a laptop\n"
        )
    if any(k in t for k in ("gym", "workout", "run", "training")):
        return (
            "Trip note: Gym or workout session.\n\n"
            "Critical Items\n"
            "- Gym access card or app login ready\n"
            "- Lock for locker if your gym needs one\n\n"
            "Normal Items\n"
            "- Water bottle\n"
            "- Separate bag for sweaty clothes\n"
        )
    return (
        "Trip note: General outing — baseline list; share dates and activity style to customize.\n\n"
        "Critical Items\n"
        "- Wallet, keys, and phone\n"
        "- Daily medications if you take any\n"
        "- ID you need for this outing\n\n"
        "Normal Items\n"
        "- Reusable water bottle\n"
        "- Light snack\n"
        "- Packable layer for changing temperature\n"
        "- Small umbrella or cap\n"
        "- Portable charger and cable\n\n"
        "Follow-up\n"
        "- What dates or season are you traveling?\n"
        "- Mostly walking outside, indoor work, or mixed — and roughly how many days?\n"
    )


def _http_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 60) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Upstream HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling API: {e.reason!s}") from e


def _http_get_json(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Checkmate/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Upstream HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling API: {e.reason!s}") from e


def _wmo_weather_label(code: int) -> str:
    labels: dict[int, str] = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Foggy",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        56: "Freezing drizzle",
        57: "Freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Rain showers",
        81: "Rain showers",
        82: "Violent rain showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with hail",
    }
    return labels.get(int(code), "Mixed conditions")


def _wmo_icon_key(code: int) -> str:
    c = int(code)
    if c in (0, 1):
        return "clear"
    if c == 2:
        return "partly_cloudy"
    if c == 3:
        return "overcast"
    if c in (45, 48):
        return "fog"
    if c in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if c in (71, 73, 75, 77, 85, 86):
        return "snow"
    if c in (95, 96, 99):
        return "storm"
    return "cloud"


def _comfort_label(apparent_c: float | None, temp_c: float) -> str:
    t = apparent_c if apparent_c is not None else temp_c
    if t >= 29:
        return "Hot"
    if t >= 24:
        return "Warm"
    if t >= 18:
        return "Comfortable"
    if t >= 10:
        return "Cool"
    return "Cold"


def _weather_packing_hint(
    code: int,
    uv: float | None,
    wind_kmh: float | None,
    is_day: bool,
    apparent_c: float | None,
) -> str:
    c = int(code)
    if c in (95, 96, 99):
        return "Storms are possible — check conditions before you leave and pack a compact umbrella."
    if c in (65, 67, 82, 86):
        return "Heavy rain or snow is possible — waterproof outer layer and dry bag for electronics help."
    if c in (51, 53, 55, 56, 57, 61, 63, 66, 80, 81):
        return "Wet weather is in the mix — a small umbrella or packable rain shell is a good idea."
    if c in (71, 73, 75, 77, 85):
        return "Cold or snowy — warm mid-layer, hat, and gloves if you will be outside for a while."
    if c in (45, 48):
        return "Low visibility — take it slow on the road and use lights or reflective gear if cycling."
    if wind_kmh is not None and wind_kmh >= 40:
        return "It is quite windy — secure loose items and add a wind-resistant layer."
    if apparent_c is not None and apparent_c <= 5:
        return "It feels cold — extra layer, warm hat, and lip balm are easy wins."
    if is_day and uv is not None and uv >= 8:
        return "UV is high today — sunscreen, sunglasses, and a hat help on longer outdoor stretches."
    if is_day and uv is not None and uv >= 5:
        return "UV is elevated — consider sunscreen if you will be outside around midday."
    return "Conditions look manageable — dress in layers you can add or remove through the day."


_WEATHER_VAGUE_LABELS = frozenset(
    {
        "",
        "near you",
        "here",
        "current location",
        "my location",
        "current",
        "local",
        "gps",
    }
)


def _format_latlon_human(lat: float, lon: float) -> str:
    la, lo = abs(lat), abs(lon)
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{la:.2f}°{ns}, {lo:.2f}°{ew}"


def _photon_place_lines(lat: float, lon: float) -> tuple[str, str | None]:
    """Reverse geocode via Photon (Komoot) — no API key."""
    try:
        url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}&lang=en"
        data = _http_get_json(url, timeout=12)
    except Exception as e:
        logger.debug("Photon reverse failed: %s", e)
        return (_format_latlon_human(lat, lon), None)
    feats = data.get("features") or []
    if not feats:
        return (_format_latlon_human(lat, lon), None)
    p = feats[0].get("properties") or {}
    street = (p.get("name") or "").strip()
    locality = (p.get("locality") or p.get("district") or "").strip()
    city = (p.get("city") or p.get("town") or p.get("village") or "").strip()
    state = (p.get("state") or "").strip()
    country = (p.get("country") or "").strip()
    core = city or locality
    parts: list[str] = []
    if core:
        parts.append(core)
    if state and state != core:
        parts.append(state)
    if country:
        parts.append(country)
    line1 = ", ".join(parts) if parts else _format_latlon_human(lat, lon)
    sub = street or None
    if not sub and locality and locality != core:
        sub = locality
    return (line1, sub)


def _resolve_gps_headline(lat: float, lon: float, label: str) -> tuple[str, str | None]:
    raw = (label or "").strip()
    if raw and raw.lower() not in _WEATHER_VAGUE_LABELS:
        return (raw, None)
    return _photon_place_lines(lat, lon)


def _geocode_place(name: str) -> tuple[float, float, str]:
    q = quote_plus(name.strip())
    if not q:
        raise ValueError("Empty place name")
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=en&format=json"
    data = _http_get_json(url)
    rows = data.get("results") or []
    if not rows:
        raise ValueError(f"Place not found: {name.strip()}")
    row = rows[0]
    lat = float(row["latitude"])
    lon = float(row["longitude"])
    loc = str(row.get("name") or name).strip()
    cc = str(row.get("country_code") or "").strip()
    admin = str(row.get("admin1") or "").strip()
    if admin and admin != loc:
        label = f"{loc} ({admin})"
    else:
        label = loc
    if cc:
        label = f"{label}, {cc}"
    return lat, lon, label


def _weather_payload_from_current(
    cur: dict[str, Any],
    lat: float,
    lon: float,
    location_label: str,
    *,
    location_detail: str | None = None,
) -> dict[str, Any]:
    if not cur:
        raise RuntimeError("Open-Meteo returned no current conditions")
    code = int(cur.get("weather_code") or 0)
    temp = float(cur.get("temperature_2m"))
    apparent = cur.get("apparent_temperature")
    apparent_f = float(apparent) if apparent is not None else None
    humidity = cur.get("relative_humidity_2m")
    hum_i = int(humidity) if humidity is not None else None
    wind = cur.get("wind_speed_10m")
    wind_f = float(wind) if wind is not None else None
    wind_dir = cur.get("wind_direction_10m")
    wind_dir_i = int(wind_dir) if wind_dir is not None else None
    uv_raw = cur.get("uv_index")
    uv = float(uv_raw) if uv_raw is not None else None
    is_day = bool(cur.get("is_day", 1))
    condition = _wmo_weather_label(code)
    comfort = _comfort_label(apparent_f, temp)
    hint = _weather_packing_hint(code, uv, wind_f, is_day, apparent_f)
    return {
        "location": location_label,
        "locationDetail": location_detail,
        "coordinatesLabel": _format_latlon_human(lat, lon),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "temp": round(temp),
        "tempUnit": "C",
        "apparentTemp": round(apparent_f) if apparent_f is not None else None,
        "condition": condition,
        "weatherCode": code,
        "iconKey": _wmo_icon_key(code),
        "humidity": hum_i,
        "windKmh": round(wind_f, 1) if wind_f is not None else None,
        "windDeg": wind_dir_i,
        "uvIndex": round(uv, 1) if uv is not None else None,
        "isDay": is_day,
        "comfort": comfort,
        "packingHint": hint,
        "source": "open-meteo",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _open_meteo_current(
    lat: float, lon: float, location_label: str, *, location_detail: str | None = None
) -> dict[str, Any]:
    params = (
        f"latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
        "wind_speed_10m,wind_direction_10m,uv_index,is_day"
        "&timezone=auto"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    data = _http_get_json(url)
    cur = data.get("current") or {}
    return _weather_payload_from_current(
        cur, lat, lon, location_label, location_detail=location_detail
    )


def _open_meteo_forecast_detail(
    lat: float, lon: float, location: str, location_detail: str | None
) -> dict[str, Any]:
    hourly = (
        "temperature_2m,precipitation_probability,weather_code,"
        "relative_humidity_2m,wind_speed_10m"
    )
    daily = (
        "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "uv_index_max,sunrise,sunset,precipitation_probability_max"
    )
    params = (
        f"latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
        "wind_speed_10m,wind_direction_10m,uv_index,is_day"
        f"&hourly={hourly}"
        f"&daily={daily}"
        "&timezone=auto"
        "&forecast_days=8"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    data = _http_get_json(url, timeout=30)
    cur = data.get("current") or {}
    if not cur:
        raise RuntimeError("Open-Meteo returned no current conditions")
    hourly_times = (data.get("hourly") or {}).get("time") or []
    h_temp = (data.get("hourly") or {}).get("temperature_2m") or []
    h_pop = (data.get("hourly") or {}).get("precipitation_probability") or []
    h_code = (data.get("hourly") or {}).get("weather_code") or []
    h_rh = (data.get("hourly") or {}).get("relative_humidity_2m") or []
    h_wind = (data.get("hourly") or {}).get("wind_speed_10m") or []
    hourly_out: list[dict[str, Any]] = []
    for i in range(min(24, len(hourly_times))):
        wc = int(h_code[i]) if i < len(h_code) else 0
        hourly_out.append(
            {
                "time": hourly_times[i],
                "temp": round(float(h_temp[i])) if i < len(h_temp) else None,
                "precipProb": int(h_pop[i]) if i < len(h_pop) else None,
                "weatherCode": wc,
                "condition": _wmo_weather_label(wc),
                "iconKey": _wmo_icon_key(wc),
                "humidity": int(h_rh[i]) if i < len(h_rh) and h_rh[i] is not None else None,
                "windKmh": round(float(h_wind[i]), 1) if i < len(h_wind) and h_wind[i] is not None else None,
            }
        )

    d_time = (data.get("daily") or {}).get("time") or []
    d_max = (data.get("daily") or {}).get("temperature_2m_max") or []
    d_min = (data.get("daily") or {}).get("temperature_2m_min") or []
    d_code = (data.get("daily") or {}).get("weather_code") or []
    d_precip = (data.get("daily") or {}).get("precipitation_sum") or []
    d_uv = (data.get("daily") or {}).get("uv_index_max") or []
    d_pop = (data.get("daily") or {}).get("precipitation_probability_max") or []
    d_sunrise = (data.get("daily") or {}).get("sunrise") or []
    d_sunset = (data.get("daily") or {}).get("sunset") or []
    daily_out: list[dict[str, Any]] = []
    for i in range(min(7, len(d_time))):
        wc = int(d_code[i]) if i < len(d_code) else 0
        daily_out.append(
            {
                "date": d_time[i],
                "max": round(float(d_max[i])) if i < len(d_max) else None,
                "min": round(float(d_min[i])) if i < len(d_min) else None,
                "weatherCode": wc,
                "condition": _wmo_weather_label(wc),
                "iconKey": _wmo_icon_key(wc),
                "precipMm": round(float(d_precip[i]), 1) if i < len(d_precip) and d_precip[i] is not None else None,
                "precipProbMax": int(d_pop[i]) if i < len(d_pop) and d_pop[i] is not None else None,
                "uvIndexMax": round(float(d_uv[i]), 1) if i < len(d_uv) and d_uv[i] is not None else None,
                "sunrise": d_sunrise[i] if i < len(d_sunrise) else None,
                "sunset": d_sunset[i] if i < len(d_sunset) else None,
            }
        )

    base = _weather_payload_from_current(
        cur, lat, lon, location, location_detail=location_detail
    )
    return {
        **base,
        "timezone": data.get("timezone"),
        "hourly": hourly_out,
        "daily": daily_out,
    }


def _weatherapi_key() -> str:
    return (os.environ.get("WEATHERAPI_KEY") or "").strip()


def _weatherapi_code_from_text(text: str) -> int:
    s = (text or "").strip().lower()
    if not s:
        return 0
    if "thunder" in s or "storm" in s:
        return 95
    if "snow" in s or "sleet" in s or "ice" in s or "blizzard" in s:
        return 73
    if "rain" in s or "drizzle" in s or "shower" in s:
        return 63
    if "fog" in s or "mist" in s or "haze" in s:
        return 45
    if "overcast" in s:
        return 3
    if "cloud" in s:
        return 2
    if "clear" in s or "sunny" in s:
        return 0
    return 1


def _weatherapi_geocode_place(name: str) -> tuple[float, float, str]:
    key = _weatherapi_key()
    if not key:
        raise RuntimeError("WEATHERAPI_KEY is not set")
    q = quote_plus(name.strip())
    if not q:
        raise ValueError("Empty place name")
    url = f"https://api.weatherapi.com/v1/search.json?key={quote_plus(key)}&q={q}"
    rows = _http_get_json(url, timeout=15)
    if not rows:
        raise ValueError(f"Place not found: {name.strip()}")
    row = rows[0] or {}
    lat = float(row.get("lat"))
    lon = float(row.get("lon"))
    city = str(row.get("name") or name).strip()
    region = str(row.get("region") or "").strip()
    country = str(row.get("country") or "").strip()
    label_parts = [city]
    if region and region != city:
        label_parts.append(region)
    if country:
        label_parts.append(country)
    return lat, lon, ", ".join(label_parts)


def _weatherapi_forecast(
    lat: float,
    lon: float,
    location_label: str,
    *,
    location_detail: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    key = _weatherapi_key()
    if not key:
        raise RuntimeError("WEATHERAPI_KEY is not set")
    q = f"{lat},{lon}"
    url = (
        f"https://api.weatherapi.com/v1/forecast.json?key={quote_plus(key)}&q={quote_plus(q)}"
        f"&days={max(1, min(days, 10))}&aqi=no&alerts=no"
    )
    data = _http_get_json(url, timeout=25)
    cur = data.get("current") or {}
    loc = data.get("location") or {}
    fc = (data.get("forecast") or {}).get("forecastday") or []
    if not cur:
        raise RuntimeError("WeatherAPI returned no current conditions")

    cond = (cur.get("condition") or {}).get("text") or "Mixed conditions"
    code = _weatherapi_code_from_text(cond)
    temp = float(cur.get("temp_c"))
    apparent = cur.get("feelslike_c")
    apparent_f = float(apparent) if apparent is not None else None
    humidity = cur.get("humidity")
    hum_i = int(humidity) if humidity is not None else None
    wind = cur.get("wind_kph")
    wind_f = float(wind) if wind is not None else None
    wind_dir = cur.get("wind_degree")
    wind_dir_i = int(wind_dir) if wind_dir is not None else None
    uv_raw = cur.get("uv")
    uv = float(uv_raw) if uv_raw is not None else None
    is_day = bool(int(cur.get("is_day") or 0))
    comfort = _comfort_label(apparent_f, temp)
    hint = _weather_packing_hint(code, uv, wind_f, is_day, apparent_f)

    out = {
        "location": location_label,
        "locationDetail": location_detail,
        "coordinatesLabel": _format_latlon_human(lat, lon),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "temp": round(temp),
        "tempUnit": "C",
        "apparentTemp": round(apparent_f) if apparent_f is not None else None,
        "condition": str(cond).strip(),
        "weatherCode": code,
        "iconKey": _wmo_icon_key(code),
        "humidity": hum_i,
        "windKmh": round(wind_f, 1) if wind_f is not None else None,
        "windDeg": wind_dir_i,
        "uvIndex": round(uv, 1) if uv is not None else None,
        "isDay": is_day,
        "comfort": comfort,
        "packingHint": hint,
        "source": "weatherapi",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    if not fc:
        return out

    hourly_out: list[dict[str, Any]] = []
    for day in fc:
        for h in (day.get("hour") or []):
            if len(hourly_out) >= 24:
                break
            h_cond = ((h.get("condition") or {}).get("text") or "").strip()
            h_code = _weatherapi_code_from_text(h_cond)
            hourly_out.append(
                {
                    "time": h.get("time"),
                    "temp": round(float(h.get("temp_c"))) if h.get("temp_c") is not None else None,
                    "precipProb": int(h.get("chance_of_rain")) if h.get("chance_of_rain") is not None else None,
                    "weatherCode": h_code,
                    "condition": h_cond or _wmo_weather_label(h_code),
                    "iconKey": _wmo_icon_key(h_code),
                    "humidity": int(h.get("humidity")) if h.get("humidity") is not None else None,
                    "windKmh": round(float(h.get("wind_kph")), 1) if h.get("wind_kph") is not None else None,
                }
            )
        if len(hourly_out) >= 24:
            break

    daily_out: list[dict[str, Any]] = []
    for day in fc[:7]:
        d = day.get("day") or {}
        d_cond = ((d.get("condition") or {}).get("text") or "").strip()
        d_code = _weatherapi_code_from_text(d_cond)
        sunrise_raw = ((day.get("astro") or {}).get("sunrise") or "").strip()
        sunset_raw = ((day.get("astro") or {}).get("sunset") or "").strip()
        date_s = str(day.get("date") or "").strip()
        daily_out.append(
            {
                "date": date_s,
                "max": round(float(d.get("maxtemp_c"))) if d.get("maxtemp_c") is not None else None,
                "min": round(float(d.get("mintemp_c"))) if d.get("mintemp_c") is not None else None,
                "weatherCode": d_code,
                "condition": d_cond or _wmo_weather_label(d_code),
                "iconKey": _wmo_icon_key(d_code),
                "precipMm": round(float(d.get("totalprecip_mm")), 1) if d.get("totalprecip_mm") is not None else None,
                "precipProbMax": int(d.get("daily_chance_of_rain")) if d.get("daily_chance_of_rain") is not None else None,
                "uvIndexMax": round(float(d.get("uv")), 1) if d.get("uv") is not None else None,
                "sunrise": f"{date_s} {sunrise_raw}".strip() if sunrise_raw else None,
                "sunset": f"{date_s} {sunset_raw}".strip() if sunset_raw else None,
            }
        )

    out["timezone"] = loc.get("tz_id")
    out["hourly"] = hourly_out
    out["daily"] = daily_out
    return out


def _tomorrowio_key() -> str:
    return (os.environ.get("TOMORROW_API_KEY") or "").strip()


def _tomorrowio_to_wmo(code_raw: Any) -> int:
    code = int(code_raw or 0)
    mapping: dict[int, int] = {
        1000: 0,   # Clear
        1100: 1,   # Mostly Clear
        1101: 2,   # Partly Cloudy
        1102: 3,   # Mostly Cloudy
        1001: 3,   # Cloudy
        2000: 45,  # Fog
        2100: 45,  # Light Fog
        4000: 51,  # Drizzle
        4001: 63,  # Rain
        4200: 61,  # Light Rain
        4201: 65,  # Heavy Rain
        5000: 73,  # Snow
        5001: 71,  # Flurries
        5100: 71,  # Light Snow
        5101: 75,  # Heavy Snow
        6000: 56,  # Freezing Drizzle
        6001: 66,  # Freezing Rain
        6200: 66,  # Light Freezing Rain
        6201: 67,  # Heavy Freezing Rain
        7000: 77,  # Ice Pellets
        7101: 77,  # Heavy Ice Pellets
        7102: 77,  # Light Ice Pellets
        8000: 95,  # Thunderstorm
    }
    return mapping.get(code, 1)


def _tomorrowio_forecast(
    lat: float,
    lon: float,
    location_label: str,
    *,
    location_detail: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    key = _tomorrowio_key()
    if not key:
        raise RuntimeError("TOMORROW_API_KEY is not set")

    fields = (
        "temperature,temperatureApparent,humidity,windSpeed,windDirection,uvIndex,"
        "weatherCode,precipitationProbability,isDayTime,temperatureMax,temperatureMin,"
        "weatherCodeMax,precipitationProbabilityAvg,sunriseTime,sunsetTime"
    )
    location_q = quote_plus(f"{lat},{lon}")
    timesteps_q = quote_plus("current,1h,1d")
    url = (
        "https://api.tomorrow.io/v4/timelines"
        f"?location={location_q}"
        f"&fields={quote_plus(fields)}"
        f"&timesteps={timesteps_q}"
        "&units=metric&timezone=auto"
        f"&apikey={quote_plus(key)}"
    )
    data = _http_get_json(url, timeout=25)
    timelines = (data.get("data") or {}).get("timelines") or []
    by_step: dict[str, list[dict[str, Any]]] = {}
    for tl in timelines:
        step = str(tl.get("timestep") or "")
        by_step[step] = list(tl.get("intervals") or [])

    current_rows = by_step.get("current") or []
    if not current_rows:
        raise RuntimeError("Tomorrow.io returned no current conditions")
    cur_vals = (current_rows[0].get("values") or {})

    t = cur_vals.get("temperature")
    temp = float(t) if t is not None else 22.0
    apparent_raw = cur_vals.get("temperatureApparent")
    apparent = float(apparent_raw) if apparent_raw is not None else None
    humidity_raw = cur_vals.get("humidity")
    humidity = int(humidity_raw) if humidity_raw is not None else None
    wind_raw = cur_vals.get("windSpeed")
    wind = float(wind_raw) if wind_raw is not None else None
    wind_dir_raw = cur_vals.get("windDirection")
    wind_dir = int(wind_dir_raw) if wind_dir_raw is not None else None
    uv_raw = cur_vals.get("uvIndex")
    uv = float(uv_raw) if uv_raw is not None else None
    is_day = bool(cur_vals.get("isDayTime"))
    code = _tomorrowio_to_wmo(cur_vals.get("weatherCode"))
    condition = _wmo_weather_label(code)
    comfort = _comfort_label(apparent, temp)
    hint = _weather_packing_hint(code, uv, wind, is_day, apparent)

    out: dict[str, Any] = {
        "location": location_label,
        "locationDetail": location_detail,
        "coordinatesLabel": _format_latlon_human(lat, lon),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "temp": round(temp),
        "tempUnit": "C",
        "apparentTemp": round(apparent) if apparent is not None else None,
        "condition": condition,
        "weatherCode": code,
        "iconKey": _wmo_icon_key(code),
        "humidity": humidity,
        "windKmh": round(wind, 1) if wind is not None else None,
        "windDeg": wind_dir,
        "uvIndex": round(uv, 1) if uv is not None else None,
        "isDay": is_day,
        "comfort": comfort,
        "packingHint": hint,
        "source": "tomorrowio",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    hourly_out: list[dict[str, Any]] = []
    for row in (by_step.get("1h") or [])[:24]:
        vals = row.get("values") or {}
        h_code = _tomorrowio_to_wmo(vals.get("weatherCode"))
        p = vals.get("precipitationProbability")
        hourly_out.append(
            {
                "time": row.get("startTime"),
                "temp": round(float(vals.get("temperature"))) if vals.get("temperature") is not None else None,
                "precipProb": int(p) if p is not None else None,
                "weatherCode": h_code,
                "condition": _wmo_weather_label(h_code),
                "iconKey": _wmo_icon_key(h_code),
                "humidity": int(vals.get("humidity")) if vals.get("humidity") is not None else None,
                "windKmh": round(float(vals.get("windSpeed")), 1) if vals.get("windSpeed") is not None else None,
            }
        )

    daily_out: list[dict[str, Any]] = []
    for row in (by_step.get("1d") or [])[: max(1, min(days, 7))]:
        vals = row.get("values") or {}
        d_code = _tomorrowio_to_wmo(vals.get("weatherCodeMax") or vals.get("weatherCode"))
        p_avg = vals.get("precipitationProbabilityAvg")
        daily_out.append(
            {
                "date": str(row.get("startTime") or "")[:10],
                "max": round(float(vals.get("temperatureMax"))) if vals.get("temperatureMax") is not None else None,
                "min": round(float(vals.get("temperatureMin"))) if vals.get("temperatureMin") is not None else None,
                "weatherCode": d_code,
                "condition": _wmo_weather_label(d_code),
                "iconKey": _wmo_icon_key(d_code),
                "precipMm": None,
                "precipProbMax": int(p_avg) if p_avg is not None else None,
                "uvIndexMax": None,
                "sunrise": vals.get("sunriseTime"),
                "sunset": vals.get("sunsetTime"),
            }
        )

    if hourly_out:
        out["hourly"] = hourly_out
    if daily_out:
        out["daily"] = daily_out
    out["timezone"] = data.get("timezone")
    return out


def _weather_current_with_fallback(
    lat: float, lon: float, location_label: str, *, location_detail: str | None = None
) -> dict[str, Any]:
    try:
        return _open_meteo_current(lat, lon, location_label, location_detail=location_detail)
    except Exception as e:
        logger.warning("Open-Meteo current failed, trying WeatherAPI: %s", e)
        try:
            return _weatherapi_forecast(
                lat, lon, location_label, location_detail=location_detail, days=1
            )
        except Exception as e2:
            logger.warning("WeatherAPI current failed, trying Tomorrow.io: %s", e2)
            return _tomorrowio_forecast(
                lat, lon, location_label, location_detail=location_detail, days=1
            )


def _weather_detail_with_fallback(
    lat: float, lon: float, location: str, location_detail: str | None
) -> dict[str, Any]:
    try:
        return _open_meteo_forecast_detail(lat, lon, location, location_detail)
    except Exception as e:
        logger.warning("Open-Meteo detail failed, trying WeatherAPI: %s", e)
        try:
            return _weatherapi_forecast(
                lat, lon, location, location_detail=location_detail, days=7
            )
        except Exception as e2:
            logger.warning("WeatherAPI detail failed, trying Tomorrow.io: %s", e2)
            return _tomorrowio_forecast(
                lat, lon, location, location_detail=location_detail, days=7
            )


def _weather_unavailable_payload(
    lat: float,
    lon: float,
    location_label: str,
    *,
    location_detail: str | None = None,
    include_detail: bool = False,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "location": location_label or "—",
        "locationDetail": location_detail,
        "coordinatesLabel": _format_latlon_human(lat, lon),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "temp": None,
        "tempUnit": "C",
        "apparentTemp": None,
        "condition": "Unavailable",
        "weatherCode": None,
        "iconKey": "cloud",
        "humidity": None,
        "windKmh": None,
        "windDeg": None,
        "uvIndex": None,
        "isDay": True,
        "comfort": "—",
        "packingHint": "Weather providers are temporarily unavailable. Try again later.",
        "source": "system-fallback",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if include_detail:
        base["timezone"] = None
        base["hourly"] = []
        base["daily"] = []
    return base


def _weather_resolve_from_request(req: Any) -> tuple[float, float, str, str | None]:
    """Parse ?lat=&lon= | ?city= | defaults. Returns (lat, lon, location, location_detail)."""
    lat_q = lon_q = None
    if "lat" in req.args or "lon" in req.args:
        try:
            lat_q = float(req.args["lat"])
            lon_q = float(req.args["lon"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid coordinates. Provide both numeric lat and lon.") from None
    city = (req.args.get("city") or "").strip()
    label = (req.args.get("label") or "").strip()

    if lat_q is not None and lon_q is not None:
        if not (-90.0 <= lat_q <= 90.0) or not (-180.0 <= lon_q <= 180.0):
            raise ValueError("Invalid coordinates.")
        loc, det = _resolve_gps_headline(lat_q, lon_q, label)
        return (lat_q, lon_q, loc, det)

    if city:
        try:
            la, lo, loc = _geocode_place(city)
            return (la, lo, loc, None)
        except Exception as e:
            logger.warning("Open-Meteo geocoding failed, trying WeatherAPI: %s", e)
            la, lo, loc = _weatherapi_geocode_place(city)
            return (la, lo, loc, None)

    lat_env = os.environ.get("WEATHER_DEFAULT_LAT", "").strip()
    lon_env = os.environ.get("WEATHER_DEFAULT_LON", "").strip()
    if lat_env and lon_env:
        la, lo = float(lat_env), float(lon_env)
        env_label = os.environ.get("WEATHER_DEFAULT_LABEL", "").strip()
        if env_label:
            return (la, lo, env_label, None)
        loc, det = _photon_place_lines(la, lo)
        return (la, lo, loc, det)

    default_city = os.environ.get("WEATHER_DEFAULT_CITY", "Shanghai").strip() or "Shanghai"
    la, lo, loc = _geocode_place(default_city)
    return (la, lo, loc, None)


def _openai_chat_completions(
    endpoint_url: str,
    api_key: str,
    model: str,
    user_message: str,
    max_tokens: int = 2200,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """OpenAI-style /v1/chat/completions (Moonshot, DeepSeek, SiliconFlow, DashScope compatible-mode, etc.)."""
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for m in prior_messages or []:
        r = m.get("role")
        c = (m.get("content") or "").strip()
        if not c or r not in ("user", "assistant"):
            continue
        msgs.append({"role": r, "content": c})
    msgs.append({"role": "user", "content": user_message})
    payload: dict[str, Any] = {
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": 0.45,
    }
    data = _http_post_json(
        endpoint_url,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        payload,
        timeout=90,
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Model returned no choices")
    content = (choices[0].get("message") or {}).get("content") or ""
    text = str(content).strip()
    if not text:
        raise RuntimeError("Model returned empty content")
    return text


def _moonshot_chat(
    user_message: str,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """Moonshot / Kimi — mainland-friendly, https://platform.moonshot.cn/"""
    api_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONSHOT_API_KEY is not set")
    url = os.environ.get(
        "MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1/chat/completions"
    ).strip()
    preferred = os.environ.get("MOONSHOT_MODEL", "").strip()
    fallbacks = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
    models: list[str] = []
    if preferred:
        models.append(preferred)
    for m in fallbacks:
        if m not in models:
            models.append(m)
    last_err: Exception | None = None
    for model in models:
        try:
            return _openai_chat_completions(
                url,
                api_key,
                model,
                user_message,
                prior_messages=prior_messages,
                system_prompt=system_prompt,
            )
        except Exception as e:
            last_err = e
            logger.warning("Moonshot model %s failed: %s", model, e)
            continue
    raise RuntimeError(f"All Moonshot models failed. Last error: {last_err}") from last_err


def _deepseek_chat(
    user_message: str,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """DeepSeek — https://platform.deepseek.com/"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    url = os.environ.get(
        "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions"
    ).strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    return _openai_chat_completions(
        url,
        api_key,
        model,
        user_message,
        prior_messages=prior_messages,
        system_prompt=system_prompt,
    )


def _siliconflow_chat(
    user_message: str,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """SiliconFlow 硅基流动 — https://siliconflow.cn (OpenAI-compatible)"""
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY is not set")
    url = os.environ.get(
        "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions"
    ).strip()
    model = os.environ.get(
        "SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct"
    ).strip()
    return _openai_chat_completions(
        url,
        api_key,
        model,
        user_message,
        prior_messages=prior_messages,
        system_prompt=system_prompt,
    )


def _dashscope_chat(
    user_message: str,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """Alibaba DashScope 通义 — compatible OpenAI API (mainland)."""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not set")
    url = os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    ).strip()
    model = os.environ.get("DASHSCOPE_MODEL", "qwen-turbo").strip()
    return _openai_chat_completions(
        url,
        api_key,
        model,
        user_message,
        prior_messages=prior_messages,
        system_prompt=system_prompt,
    )


def _gemini_chat(
    user_message: str,
    prior_messages: list[dict[str, str]] | None = None,
    system_prompt: str = AI_SYSTEM_PROMPT,
) -> str:
    """Google Gemini — free tier API key from https://aistudio.google.com/apikey"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={quote_plus(api_key)}"
    )
    contents: list[dict[str, Any]] = []
    for m in prior_messages or []:
        r = m.get("role")
        c = (m.get("content") or "").strip()
        if not c or r not in ("user", "assistant"):
            continue
        gem_role = "user" if r == "user" else "model"
        contents.append({"role": gem_role, "parts": [{"text": c}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 3072,
            "temperature": 0.45,
        },
    }
    data = _http_post_json(
        url,
        {"Content-Type": "application/json"},
        payload,
        timeout=60,
    )
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    text = "\n".join(t for t in texts if t).strip()
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


def _short_ai_err(e: BaseException) -> str:
    s = str(e)
    return s[:280] + ("…" if len(s) > 280 else "")


def _contains_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _preferred_reply_language(user_message: str) -> str:
    """Decide target response language from the latest user message."""
    msg = (user_message or "").strip()
    if not msg:
        return "en"
    if _contains_cjk(msg):
        return "zh"
    return "en"


def _build_system_prompt_for_language(lang: str) -> str:
    if lang == "zh":
        return (
            AI_SYSTEM_PROMPT
            + "\n\nLanguage rule override: Reply in Simplified Chinese for content lines, "
            "but keep section headings exactly as: Trip note:, Critical Items, Normal Items, Tips, Follow-up. "
            "Do not use markdown headings like ###."
        )
    return (
        AI_SYSTEM_PROMPT
        + "\n\nLanguage rule override: Reply in English only. "
        "Do not use Chinese characters. "
        "Do not use markdown headings like ###."
    )


def _sanitize_assistant_text(text: str) -> str:
    """Remove control chars that may break rendering, keep newlines/tabs."""
    if not isinstance(text, str):
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    s = s.replace("�", "")
    s = "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return s.strip()


_NON_PACKING_LINE_PATTERNS = (
    r"(hotel|住宿|民宿|attraction|景点|景點|故宫|天安门|itinerary|行程安排|行程建议|行程建議|"
    r"restaurant|餐厅|餐廳|美食|烤鸭|烤鴨|transport|交通|地铁|地鐵|公交|出租车|網約車|网约车|"
    r"sightseeing|参观|參觀|visit\s+the|去.*玩)"
)


def _drop_non_packing_bullets(reply: str) -> str:
    """Remove obvious itinerary/attraction bullets when model drifts away from packing domain."""
    lines = (reply or "").split("\n")
    out: list[str] = []
    for ln in lines:
        st = ln.strip()
        if re.match(r"^[-•]\s+", st):
            body = re.sub(r"^[-•]\s+", "", st).strip().lower()
            if re.search(_NON_PACKING_LINE_PATTERNS, body):
                continue
        out.append(ln)
    return "\n".join(out).strip()


# When AI_PROVIDER is empty, try keys in this order (mainland-friendly first).
AI_AUTO_ORDER = [
    "moonshot",
    "deepseek",
    "siliconflow",
    "dashscope",
    "gemini",
]


def _ai_reply(
    user_message: str, prior_messages: list[dict[str, str]] | None = None
) -> dict:
    """
    Returns dict: reply, source (moonshot|deepseek|siliconflow|dashscope|gemini|rules), hint.
    prior_messages: optional OpenAI-style [{role: user|assistant, content}, ...] without the latest user turn.
    """
    msg = (user_message or "").strip()
    if not msg:
        return {
            "reply": _sanitize_assistant_text(_assistant_reply_rules("")),
            "source": "rules",
            "hint": None,
        }
    if len(msg) > MAX_USER_AI_MESSAGE_CHARS:
        msg = msg[:MAX_USER_AI_MESSAGE_CHARS]

    if _user_message_needs_clarification(msg):
        return {
            "reply": _sanitize_assistant_text(_assistant_clarification_reply()),
            "source": "rules",
            "hint": None,
        }

    if _travel_intent_without_place(msg):
        return {
            "reply": _sanitize_assistant_text(_assistant_need_destination_reply()),
            "source": "rules",
            "hint": None,
        }

    reply_lang = _preferred_reply_language(msg)
    system_prompt = _build_system_prompt_for_language(reply_lang)

    def _return_ai(text: str, source: str) -> dict:
        sanitized = _sanitize_assistant_text(text)
        focused = _drop_non_packing_bullets(sanitized)
        no_tips = _remove_tips_section_when_packing_list(focused)
        deduped = _dedupe_followup_sections(no_tips)
        cleaned = _strip_trailing_question_bullets_misplaced(deduped)
        return {
            "reply": _ensure_followup_when_place_without_timing(cleaned, msg),
            "source": source,
            "hint": None,
        }

    provider = os.environ.get("AI_PROVIDER", "").strip().lower()
    keys = {
        "moonshot": os.environ.get("MOONSHOT_API_KEY", "").strip(),
        "deepseek": os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        "siliconflow": os.environ.get("SILICONFLOW_API_KEY", "").strip(),
        "dashscope": os.environ.get("DASHSCOPE_API_KEY", "").strip(),
        "gemini": os.environ.get("GEMINI_API_KEY", "").strip(),
    }
    callers = {
        "moonshot": _moonshot_chat,
        "deepseek": _deepseek_chat,
        "siliconflow": _siliconflow_chat,
        "dashscope": _dashscope_chat,
        "gemini": _gemini_chat,
    }

    if provider in callers:
        k = keys.get(provider, "")
        if not k:
            return {
                "reply": _sanitize_assistant_text(_assistant_reply_rules(msg)),
                "source": "rules",
                "hint": f"AI_PROVIDER is '{provider}' but the matching API key is not set in .env",
            }
        try:
            return _return_ai(
                callers[provider](msg, prior_messages, system_prompt=system_prompt),
                provider,
            )
        except Exception as e:
            logger.warning("Explicit AI provider %s failed: %s", provider, e)
            return {
                "reply": _sanitize_assistant_text(_assistant_reply_rules(msg)),
                "source": "rules",
                "hint": _short_ai_err(e),
            }

    last_err: BaseException | None = None
    for name in AI_AUTO_ORDER:
        if not keys.get(name):
            continue
        try:
            return _return_ai(
                callers[name](msg, prior_messages, system_prompt=system_prompt),
                name,
            )
        except Exception as e:
            last_err = e
            logger.warning("AI provider %s failed: %s", name, e)
            continue

    if last_err:
        return {
            "reply": _sanitize_assistant_text(_assistant_reply_rules(msg)),
            "source": "rules",
            "hint": _short_ai_err(last_err),
        }
    return {
        "reply": _sanitize_assistant_text(_assistant_reply_rules(msg)),
        "source": "rules",
        "hint": "No AI API keys in .env — add MOONSHOT_API_KEY, DEEPSEEK_API_KEY, SILICONFLOW_API_KEY, DASHSCOPE_API_KEY, or GEMINI_API_KEY.",
    }


def _ensure_prefs_json_column() -> None:
    """Upgrade older MySQL tables that lack app_preferences.prefs_json."""
    try:
        insp = inspect(db.engine)
        if "app_preferences" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("app_preferences")}
        if "prefs_json" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE app_preferences ADD COLUMN prefs_json JSON NULL")
            )
        logger.info("Added app_preferences.prefs_json column.")
    except Exception as e:
        logger.debug("prefs_json column ensure skipped: %s", e)


def _cleanup_friend_from_scenarios(user_id: int, friend_id: str) -> None:
    """Drop friend from collaborators; reassign their items to 'me'."""
    rows = Scenario.query.filter_by(user_id=user_id).all()
    for sc in rows:
        old_collab = list(sc.collaborators or [])
        collab = [c for c in old_collab if c != friend_id]
        if collab != old_collab:
            sc.collaborators = collab
        items_in = sc.items or []
        new_items: list[Any] = []
        changed_items = False
        for it in items_in:
            if isinstance(it, dict) and it.get("assignedTo") == friend_id:
                new_items.append({**it, "assignedTo": "me"})
                changed_items = True
            else:
                new_items.append(it)
        if changed_items:
            sc.items = new_items


def _collaborator_user_ids(collaborators: list[Any]) -> set[int]:
    """Parse scenario.collaborators entries like 'u12' into user ids."""
    out: set[int] = set()
    for fid in collaborators or []:
        if isinstance(fid, str) and fid.startswith("u"):
            try:
                out.add(int(fid[1:]))
            except ValueError:
                continue
    return out


def _sync_edit_shares_for_collaborators(
    owner_user_id: int,
    scenario_id: str,
    collaborators: list[Any],
    revoke_edit_user_ids: set[int] | None = None,
) -> None:
    """Grant can_edit shares for trip collaborators; downgrade edit for removed collaborators only.

    Must NOT treat an empty collaborators list as 'remove everyone': explicit shares
    from POST /share (with or without edit) are separate from collaborators.
    """
    want_ids = _collaborator_user_ids(collaborators)
    existing = ScenarioShare.query.filter_by(owner_user_id=owner_user_id, scenario_id=scenario_id).all()
    existing_by_uid = {r.shared_with_user_id: r for r in existing}

    for uid in want_ids:
        r = existing_by_uid.get(uid)
        if r:
            r.can_edit = True
        else:
            n = ScenarioShare(
                owner_user_id=owner_user_id,
                scenario_id=scenario_id,
                shared_with_user_id=uid,
                can_edit=True,
            )
            db.session.add(n)
            existing_by_uid[uid] = n

    for uid in set(revoke_edit_user_ids or set()):
        r = existing_by_uid.get(uid)
        if r and r.can_edit:
            r.can_edit = False


def _validate_items_assignees(items: Any, allowed_friend_ids: set[str]) -> str | None:
    if items is None:
        return None
    if not isinstance(items, list):
        return "items must be a list"
    for it in items:
        if not isinstance(it, dict):
            continue
        a = it.get("assignedTo")
        if not a or a == "me":
            continue
        if a not in allowed_friend_ids:
            return "assignedTo must be 'me' or one of the scenario collaborators"
    return None


ALLOWED_AVATAR_STYLES = {
    "notionists",
    "avataaars",
    "bottts",
    "micah",
    "fun-emoji",
    "adventurer",
    "adventurer-neutral",
    "big-ears",
    "big-smile",
    "croodles",
    "identicon",
    "lorelei",
    "open-peeps",
    "thumbs",
}


def _safe_avatar_style(style: str | None) -> str:
    s = (style or "").strip().lower()
    return s if s in ALLOWED_AVATAR_STYLES else "notionists"


def _dicebear_avatar(username: str, style: str | None = None) -> str:
    avatar_style = _safe_avatar_style(style)
    return f"https://api.dicebear.com/7.x/{quote_plus(avatar_style)}/svg?seed={quote_plus(username)}"


def _ensure_friend_mirror_row(owner_user_id: int, target: User) -> Friend:
    fid = f"u{target.id}"
    row = Friend.query.filter_by(user_id=owner_user_id, id=fid).first()
    av = _dicebear_avatar(target.username, target.avatar_style)
    dn = (target.display_name or "").strip()
    label = dn if dn else target.username
    if row:
        row.name = label
        row.avatar = av
        row.linked_user_id = target.id
        return row
    row = Friend(
        user_id=owner_user_id,
        id=fid,
        name=label,
        avatar=av,
        linked_user_id=target.id,
    )
    db.session.add(row)
    return row


def _remove_registered_friendship(a_uid: int, b_uid: int) -> None:
    Friend.query.filter(
        and_(Friend.user_id == a_uid, Friend.linked_user_id == b_uid)
    ).delete(synchronize_session=False)
    Friend.query.filter(
        and_(Friend.user_id == b_uid, Friend.linked_user_id == a_uid)
    ).delete(synchronize_session=False)
    ScenarioShare.query.filter(
        or_(
            and_(
                ScenarioShare.owner_user_id == a_uid,
                ScenarioShare.shared_with_user_id == b_uid,
            ),
            and_(
                ScenarioShare.owner_user_id == b_uid,
                ScenarioShare.shared_with_user_id == a_uid,
            ),
        )
    ).delete(synchronize_session=False)
    FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == a_uid, FriendRequest.to_user_id == b_uid),
            and_(FriendRequest.from_user_id == b_uid, FriendRequest.to_user_id == a_uid),
        )
    ).delete(synchronize_session=False)


def _purge_unlinked_friend_rows() -> None:
    """Remove label-only friend rows (no linked_user_id) and scrub scenario references."""
    try:
        stale = Friend.query.filter(Friend.linked_user_id.is_(None)).all()
        if not stale:
            return
        by_user: dict[int, set[str]] = {}
        for f in stale:
            by_user.setdefault(f.user_id, set()).add(f.id)
        for uid, dead_ids in by_user.items():
            for sc in Scenario.query.filter_by(user_id=uid).all():
                collab_old = list(sc.collaborators or [])
                collab_new = [c for c in collab_old if c not in dead_ids]
                if collab_new != collab_old:
                    sc.collaborators = collab_new
                items_in = list(sc.items or [])
                new_items: list[Any] = []
                changed = False
                for it in items_in:
                    if isinstance(it, dict) and it.get("assignedTo") in dead_ids:
                        new_items.append({**it, "assignedTo": "me"})
                        changed = True
                    else:
                        new_items.append(it)
                if changed:
                    sc.items = new_items
        Friend.query.filter(Friend.linked_user_id.is_(None)).delete(synchronize_session=False)
        db.session.commit()
        logger.info("Purged %d unlinked friend rows.", len(stale))
    except Exception as e:
        db.session.rollback()
        logger.warning("purge unlinked friends skipped: %s", e)


def _ensure_friends_linked_user_column() -> None:
    try:
        insp = inspect(db.engine)
        if "friends" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("friends")}
        if "linked_user_id" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE friends ADD COLUMN linked_user_id INT NULL"))
        logger.info("Added friends.linked_user_id column.")
    except Exception as e:
        logger.debug("friends.linked_user_id ensure skipped: %s", e)


def _ensure_user_display_name_column() -> None:
    try:
        insp = inspect(db.engine)
        if "users" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("users")}
        if "display_name" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR(120) NULL"))
        logger.info("Added users.display_name column.")
    except Exception as e:
        logger.debug("users.display_name ensure skipped: %s", e)


def _ensure_user_avatar_style_column() -> None:
    try:
        insp = inspect(db.engine)
        if "users" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("users")}
        if "avatar_style" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_style VARCHAR(40) NULL"))
        logger.info("Added users.avatar_style column.")
    except Exception as e:
        logger.debug("users.avatar_style ensure skipped: %s", e)


def _ensure_scenario_shares_can_edit_column() -> None:
    try:
        insp = inspect(db.engine)
        if "scenario_shares" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("scenario_shares")}
        if "can_edit" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE scenario_shares ADD COLUMN can_edit BOOLEAN NOT NULL DEFAULT 0"))
        logger.info("Added scenario_shares.can_edit column.")
    except Exception as e:
        logger.debug("scenario_shares.can_edit ensure skipped: %s", e)


def _ensure_scenarios_archived_column() -> None:
    try:
        insp = inspect(db.engine)
        if "scenarios" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("scenarios")}
        if "archived" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE scenarios ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"))
        logger.info("Added scenarios.archived column.")
    except Exception as e:
        logger.debug("scenarios.archived ensure skipped: %s", e)


def _ensure_scenarios_trip_datetime_columns() -> None:
    try:
        insp = inspect(db.engine)
        if "scenarios" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("scenarios")}
        with db.engine.begin() as conn:
            if "trip_start_at" not in col_names:
                conn.execute(text("ALTER TABLE scenarios ADD COLUMN trip_start_at DATETIME NULL"))
                logger.info("Added scenarios.trip_start_at column.")
            if "trip_end_at" not in col_names:
                conn.execute(text("ALTER TABLE scenarios ADD COLUMN trip_end_at DATETIME NULL"))
                logger.info("Added scenarios.trip_end_at column.")
    except Exception as e:
        logger.debug("scenarios.trip datetime ensure skipped: %s", e)


def _ensure_history_records_scenario_id_column() -> None:
    try:
        insp = inspect(db.engine)
        if "history_records" not in insp.get_table_names():
            return
        col_names = {c["name"] for c in insp.get_columns("history_records")}
        if "scenario_id" in col_names:
            return
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE history_records ADD COLUMN scenario_id VARCHAR(64) NULL"))
        logger.info("Added history_records.scenario_id column.")
    except Exception as e:
        logger.debug("history_records.scenario_id ensure skipped: %s", e)


def _history_has_scenario_id_column() -> bool:
    try:
        insp = inspect(db.engine)
        if "history_records" not in insp.get_table_names():
            return False
        col_names = {c["name"] for c in insp.get_columns("history_records")}
        return "scenario_id" in col_names
    except Exception:
        return False


def create_app() -> Flask:
    app = Flask(__name__)
    _mysql_host_env = os.environ.get("MYSQL_HOST") or ""
    print(f"[checkmate] MYSQL_HOST env first 5 chars: {_mysql_host_env[:5]!r}")
    database_uri = _database_uri()
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = _sqlalchemy_engine_options(database_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False

    db.init_app(app)
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    with app.app_context():
        db.create_all()
        _ensure_prefs_json_column()
        _ensure_friends_linked_user_column()
        _ensure_user_display_name_column()
        _ensure_user_avatar_style_column()
        _ensure_scenario_shares_can_edit_column()
        _ensure_scenarios_archived_column()
        _ensure_scenarios_trip_datetime_columns()
        _ensure_history_records_scenario_id_column()
        _purge_unlinked_friend_rows()

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(force=True, silent=True) or {}
        username = _validate_username(data.get("username"))
        password = data.get("password")
        if not username:
            return jsonify(
                {"error": "Username must be 3–32 characters: lowercase letters, digits, or underscore."}
            ), 400
        if not _validate_password(password):
            return jsonify({"error": "Password must be at least 6 characters."}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "That username is already taken."}), 409
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        seed_new_user(user.id)
        token = _issue_token(user.id)
        return (
            jsonify({"token": token, "user": user.to_public_dict()}),
            201,
        )

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = _validate_username(data.get("username"))
        password = data.get("password")
        if not username or not password:
            return jsonify({"error": "Please enter username and password."}), 400
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid username or password."}), 401
        token = _issue_token(user.id)
        return jsonify({"token": token, "user": user.to_public_dict()})

    @app.get("/api/me")
    @require_auth
    def me():
        return jsonify(g.current_user.to_public_dict())

    @app.put("/api/me")
    @require_auth
    def update_me():
        data = request.get_json(force=True, silent=True) or {}
        changed = False
        if "display_name" in data:
            s = str(data.get("display_name") or "").strip()
            if len(s) > 48:
                return jsonify({"error": "Display name too long (max 48)."}), 400
            g.current_user.display_name = s if s else None
            changed = True
        if "avatar_style" in data:
            style = _safe_avatar_style(str(data.get("avatar_style") or ""))
            g.current_user.avatar_style = style
            changed = True
        if changed:
            db.session.commit()
        return jsonify(g.current_user.to_public_dict())

    @app.put("/api/me/password")
    @require_auth
    def update_my_password():
        data = request.get_json(force=True, silent=True) or {}
        cur = data.get("current_password")
        new_pw = data.get("new_password")
        if not isinstance(cur, str) or not check_password_hash(
            g.current_user.password_hash, cur
        ):
            return jsonify({"error": "Current password is incorrect."}), 400
        if not _validate_password(new_pw):
            return jsonify({"error": "New password must be at least 6 characters."}), 400
        g.current_user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        return jsonify({"ok": True})

    @app.delete("/api/me")
    @require_auth
    def delete_me():
        uid = g.current_user.id
        u = User.query.get(uid)
        if u:
            db.session.delete(u)
            db.session.commit()
        return "", 204

    @app.get("/api/users/lookup")
    @require_auth
    def lookup_user():
        raw = (request.args.get("username") or "").strip().lower()
        u = _validate_username(raw)
        if not u:
            return jsonify({"found": False, "error": "Invalid username format."}), 400
        if u == g.current_user.username:
            return jsonify({"found": False, "error": "That is your own username."}), 400
        target = User.query.filter_by(username=u).first()
        if not target:
            return jsonify({"found": False})
        dn = (target.display_name or "").strip()
        return jsonify(
            {
                "found": True,
                "user": {
                    "username": target.username,
                    "display_name": dn or None,
                    "avatar": _dicebear_avatar(target.username, target.avatar_style),
                    "avatar_style": _safe_avatar_style(target.avatar_style),
                },
            }
        )

    @app.post("/api/friends/requests")
    @require_auth
    def create_friend_request():
        uid = g.current_user.id
        payload = request.get_json(force=True, silent=True) or {}
        u = _validate_username(payload.get("username"))
        if not u:
            return jsonify({"error": "username is required (3–32 lowercase letters, digits, underscore)."}), 400
        if u == g.current_user.username:
            return jsonify({"error": "You cannot add yourself."}), 400
        target = User.query.filter_by(username=u).first()
        if not target:
            return jsonify({"error": "No user with that username."}), 404
        if Friend.query.filter_by(user_id=uid, linked_user_id=target.id).first():
            return jsonify({"error": "You are already friends with this user."}), 409
        if FriendRequest.query.filter_by(
            from_user_id=uid, to_user_id=target.id, status="pending"
        ).first():
            return jsonify({"error": "A request is already pending."}), 409
        reverse = FriendRequest.query.filter_by(
            from_user_id=target.id, to_user_id=uid, status="pending"
        ).first()
        if reverse:
            return jsonify(
                {
                    "error": "That user already sent you a request.",
                    "incoming_request_id": reverse.id,
                }
            ), 409
        row = FriendRequest(from_user_id=uid, to_user_id=target.id, status="pending")
        db.session.add(row)
        db.session.commit()
        d = row.to_dict()
        d["to_username"] = target.username
        return jsonify(d), 201

    @app.get("/api/friends/requests")
    @require_auth
    def list_friend_requests():
        uid = g.current_user.id
        direction = (request.args.get("direction") or "incoming").strip().lower()
        if direction == "outgoing":
            rows = FriendRequest.query.filter_by(from_user_id=uid, status="pending").order_by(
                FriendRequest.id.desc()
            ).all()
            out = []
            for r in rows:
                tu = User.query.get(r.to_user_id)
                d = r.to_dict()
                d["to_username"] = tu.username if tu else "?"
                out.append(d)
            return jsonify(out)
        rows = FriendRequest.query.filter_by(to_user_id=uid, status="pending").order_by(
            FriendRequest.id.desc()
        ).all()
        out = []
        for r in rows:
            fu = User.query.get(r.from_user_id)
            d = r.to_dict()
            d["from_username"] = fu.username if fu else "?"
            out.append(d)
        return jsonify(out)

    @app.post("/api/friends/requests/<int:request_id>/accept")
    @require_auth
    def accept_friend_request(request_id: int):
        uid = g.current_user.id
        req = FriendRequest.query.filter_by(id=request_id, to_user_id=uid, status="pending").first()
        if not req:
            return jsonify({"error": "Request not found or already handled."}), 404
        a = User.query.get(req.from_user_id)
        b = User.query.get(req.to_user_id)
        if not a or not b:
            return jsonify({"error": "Invalid request."}), 400
        db.session.delete(req)
        _ensure_friend_mirror_row(a.id, b)
        _ensure_friend_mirror_row(b.id, a)
        db.session.commit()
        return jsonify({"ok": True})

    @app.post("/api/friends/requests/<int:request_id>/decline")
    @require_auth
    def decline_friend_request(request_id: int):
        uid = g.current_user.id
        req = FriendRequest.query.filter_by(id=request_id, to_user_id=uid, status="pending").first()
        if not req:
            return jsonify({"error": "Request not found or already handled."}), 404
        db.session.delete(req)
        db.session.commit()
        return jsonify({"ok": True})

    @app.post("/api/scenarios/<scenario_id>/share")
    @require_auth
    def share_scenario(scenario_id: str):
        uid = g.current_user.id
        payload = request.get_json(force=True, silent=True) or {}
        u = _validate_username(payload.get("username"))
        can_edit = bool(payload.get("can_edit"))
        if not u:
            return jsonify({"error": "username is required."}), 400
        target = User.query.filter_by(username=u).first()
        if not target:
            return jsonify({"error": "No user with that username."}), 404
        if target.id == uid:
            return jsonify({"error": "Cannot share with yourself."}), 400
        row = Scenario.query.filter_by(user_id=uid, id=scenario_id).first()
        if not row:
            return jsonify({"error": "Scenario not found."}), 404
        if not Friend.query.filter_by(user_id=uid, linked_user_id=target.id).first():
            return jsonify({"error": "You can only share with accepted friends."}), 403
        existing = ScenarioShare.query.filter_by(
            owner_user_id=uid, scenario_id=scenario_id, shared_with_user_id=target.id
        ).first()
        if existing:
            if existing.can_edit != can_edit:
                existing.can_edit = can_edit
                db.session.commit()
            return jsonify({"ok": True, "already": True, "can_edit": bool(existing.can_edit)})
        db.session.add(
            ScenarioShare(
                owner_user_id=uid,
                scenario_id=scenario_id,
                shared_with_user_id=target.id,
                can_edit=can_edit,
            )
        )
        db.session.commit()
        return jsonify({"ok": True, "can_edit": can_edit}), 201

    @app.delete("/api/scenarios/<scenario_id>/share")
    @require_auth
    def unshare_scenario(scenario_id: str):
        uid = g.current_user.id
        data = request.get_json(force=True, silent=True) or {}
        raw = request.args.get("username") or data.get("username")
        u = _validate_username(raw or "")
        if not u:
            return jsonify({"error": "Pass username as query string or JSON body."}), 400
        target = User.query.filter_by(username=u).first()
        if not target:
            return jsonify({"error": "No user with that username."}), 404
        deleted = (
            ScenarioShare.query.filter_by(
                owner_user_id=uid,
                scenario_id=scenario_id,
                shared_with_user_id=target.id,
            ).delete(synchronize_session=False)
        )
        db.session.commit()
        if not deleted:
            return jsonify({"error": "Share not found."}), 404
        return "", 204

    @app.post("/api/assistant/reply")
    @require_auth
    def assistant_reply():
        data = request.get_json(force=True, silent=True) or {}
        msg = (data.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "message is required"}), 400
        prior = _normalize_conversation_for_api(data.get("conversation"))
        out = _ai_reply(msg, prior)
        body = {"reply": out["reply"], "source": out["source"]}
        if out.get("hint"):
            body["hint"] = out["hint"]
        return jsonify(body)

    @app.get("/api/assistant/status")
    @require_auth
    def assistant_status():
        """Which AI backends have keys loaded (no secrets returned)."""
        return jsonify(
            {
                "ai_provider": os.environ.get("AI_PROVIDER", "").strip(),
                "auto_order": AI_AUTO_ORDER,
                "moonshot_configured": bool(os.environ.get("MOONSHOT_API_KEY", "").strip()),
                "deepseek_configured": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
                "siliconflow_configured": bool(os.environ.get("SILICONFLOW_API_KEY", "").strip()),
                "dashscope_configured": bool(os.environ.get("DASHSCOPE_API_KEY", "").strip()),
                "gemini_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
            }
        )

    @app.get("/api/weather")
    @require_auth
    def get_weather():
        """
        Live weather via Open-Meteo (no API key). Query: lat & lon, or city=PlaceName.
        If omitted, uses WEATHER_DEFAULT_CITY or WEATHER_DEFAULT_LAT/LON from environment.
        GPS requests resolve a real place name via reverse geocode when label is vague.
        """
        try:
            la, lo, loc, det = _weather_resolve_from_request(request)
            return jsonify(_weather_current_with_fallback(la, lo, loc, location_detail=det))
        except ValueError as e:
            msg = str(e)
            code = 400 if "Invalid coordinates" in msg else 404
            return jsonify({"error": msg}), code
        except Exception as e:
            logger.warning("Weather fetch failed: %s", e)
            try:
                la, lo, loc, det = _weather_resolve_from_request(request)
            except Exception:
                la, lo, loc, det = 0.0, 0.0, "—", None
            return jsonify(_weather_unavailable_payload(la, lo, loc, location_detail=det))

    @app.get("/api/weather/detail")
    @require_auth
    def get_weather_detail():
        """Extended forecast: 24h hourly steps + 7-day daily (same query rules as /api/weather)."""
        try:
            la, lo, loc, det = _weather_resolve_from_request(request)
            return jsonify(_weather_detail_with_fallback(la, lo, loc, det))
        except ValueError as e:
            msg = str(e)
            code = 400 if "Invalid coordinates" in msg else 404
            return jsonify({"error": msg}), code
        except Exception as e:
            logger.warning("Weather detail failed: %s", e)
            try:
                la, lo, loc, det = _weather_resolve_from_request(request)
            except Exception:
                la, lo, loc, det = 0.0, 0.0, "—", None
            return jsonify(
                _weather_unavailable_payload(
                    la, lo, loc, location_detail=det, include_detail=True
                )
            )

    @app.get("/api/scenarios")
    @require_auth
    def list_scenarios():
        uid = g.current_user.id
        rows = Scenario.query.filter_by(user_id=uid, archived=False).all()
        out: list[dict[str, Any]] = []
        for r in _sort_scenarios(rows):
            d = dict(r.to_dict())
            d["access"] = "owner"
            share_rows = ScenarioShare.query.filter_by(
                owner_user_id=uid, scenario_id=r.id
            ).all()
            recipients: list[dict[str, Any]] = []
            for sh in share_rows:
                su = User.query.get(sh.shared_with_user_id)
                if su:
                    recipients.append(
                        {
                            "username": su.username,
                            "user_id": su.id,
                            "can_edit": bool(sh.can_edit),
                            "avatar": _dicebear_avatar(su.username, su.avatar_style),
                        }
                    )
            d["share_recipients"] = recipients
            out.append(d)
        shares = ScenarioShare.query.filter_by(shared_with_user_id=uid).all()
        for sh in shares:
            row = Scenario.query.filter_by(user_id=sh.owner_user_id, id=sh.scenario_id).first()
            if not row or row.archived:
                continue
            owner = User.query.get(sh.owner_user_id)
            d = dict(row.to_dict())
            d["access"] = "shared_edit" if sh.can_edit else "shared"
            d["owner_user_id"] = sh.owner_user_id
            d["owner_username"] = owner.username if owner else "?"
            d["owner_avatar"] = (
                _dicebear_avatar(owner.username, owner.avatar_style) if owner else None
            )
            d["share_recipients"] = []
            out.append(d)
        return jsonify(out)

    @app.post("/api/scenarios")
    @require_auth
    def create_scenario():
        uid = g.current_user.id
        payload = request.get_json(force=True, silent=True) or {}
        name = (payload.get("name") or "").strip()
        items = payload.get("items") or []
        if not name or not items:
            return jsonify({"error": "name and items required"}), 400
        sid = str(payload.get("id") or _new_id("s"))
        icon = payload.get("icon") or "Backpack"
        theme = payload.get("theme")
        try:
            trip_start_at = _parse_iso_datetime(payload.get("trip_start_at"))
            trip_end_at = _parse_iso_datetime(payload.get("trip_end_at"))
        except Exception:
            return jsonify({"error": "Invalid trip date/time format."}), 400
        if _is_past_datetime(trip_start_at):
            return jsonify({"error": "Trip start time cannot be in the past."}), 400
        if trip_start_at and trip_end_at and trip_end_at < trip_start_at:
            return jsonify({"error": "Trip end time must be after start time."}), 400
        row = Scenario(
            user_id=uid,
            id=sid,
            name=name,
            icon=icon,
            theme=theme,
            type="custom",
            items=items,
            collaborators=[],
            archived=False,
            trip_start_at=trip_start_at,
            trip_end_at=trip_end_at,
        )
        db.session.add(row)
        db.session.commit()
        return jsonify(row.to_dict()), 201

    @app.get("/api/scenarios/<scenario_id>")
    @require_auth
    def get_scenario(scenario_id: str):
        uid = g.current_user.id
        row = Scenario.query.filter_by(user_id=uid, id=scenario_id).first()
        if not row:
            sh = ScenarioShare.query.filter_by(
                shared_with_user_id=uid, scenario_id=scenario_id
            ).first()
            if not sh:
                return jsonify({"error": "not found"}), 404
            row = Scenario.query.filter_by(user_id=sh.owner_user_id, id=scenario_id).first()
            if not row:
                return jsonify({"error": "not found"}), 404
            owner = User.query.get(sh.owner_user_id)
            d = dict(row.to_dict())
            d["access"] = "shared_edit" if sh.can_edit else "shared"
            d["owner_user_id"] = sh.owner_user_id
            d["owner_username"] = owner.username if owner else "?"
            d["owner_avatar"] = (
                _dicebear_avatar(owner.username, owner.avatar_style) if owner else None
            )
            d["share_recipients"] = []
            return jsonify(d)

        d = dict(row.to_dict())
        d["access"] = "owner"
        share_rows = ScenarioShare.query.filter_by(owner_user_id=uid, scenario_id=row.id).all()
        recipients: list[dict[str, Any]] = []
        for sh in share_rows:
            su = User.query.get(sh.shared_with_user_id)
            if su:
                recipients.append(
                    {
                        "username": su.username,
                        "user_id": su.id,
                        "can_edit": bool(sh.can_edit),
                        "avatar": _dicebear_avatar(su.username, su.avatar_style),
                    }
                )
        d["share_recipients"] = recipients
        return jsonify(d)

    @app.put("/api/scenarios/<scenario_id>")
    @require_auth
    def update_scenario(scenario_id: str):
        uid = g.current_user.id
        row = Scenario.query.filter_by(user_id=uid, id=scenario_id).first()
        if not row:
            sh = ScenarioShare.query.filter_by(
                shared_with_user_id=uid, scenario_id=scenario_id
            ).first()
            if not sh:
                return jsonify({"error": "not found"}), 404
            if not sh.can_edit:
                return jsonify({"error": "This list is shared with you as view-only."}), 403
            row = Scenario.query.filter_by(user_id=sh.owner_user_id, id=scenario_id).first()
            if not row:
                return jsonify({"error": "not found"}), 404
        payload = request.get_json(force=True, silent=True) or {}
        is_owner = row.user_id == uid
        allowed = ("items",) if not is_owner else (
            "name",
            "icon",
            "theme",
            "items",
            "collaborators",
            "archived",
            "trip_start_at",
            "trip_end_at",
        )
        if not is_owner and any(k in payload for k in ("name", "icon", "theme", "collaborators", "type", "trip_start_at", "trip_end_at")):
            return jsonify({"error": "Only the owner can edit list settings."}), 403

        # Validate assignees: collaborators, list owner, and anyone this scenario is shared with.
        collab = list(row.collaborators or [])
        allowed_friend_ids = set(["me", *[c for c in collab if isinstance(c, str)]])
        allowed_friend_ids.add(f"u{row.user_id}")
        for shr in ScenarioShare.query.filter_by(owner_user_id=row.user_id, scenario_id=scenario_id).all():
            allowed_friend_ids.add(f"u{shr.shared_with_user_id}")
        if "items" in payload:
            msg = _validate_items_assignees(payload.get("items"), allowed_friend_ids)
            if msg:
                return jsonify({"error": msg}), 400

        prev_collab_uids = _collaborator_user_ids(row.collaborators)

        if is_owner and ("trip_start_at" in payload or "trip_end_at" in payload):
            try:
                next_start = _parse_iso_datetime(payload.get("trip_start_at", row.trip_start_at))
                next_end = _parse_iso_datetime(payload.get("trip_end_at", row.trip_end_at))
            except Exception:
                return jsonify({"error": "Invalid trip date/time format."}), 400
            if "trip_start_at" in payload and _is_past_datetime(next_start):
                return jsonify({"error": "Trip start time cannot be in the past."}), 400
            if next_start and next_end and next_end < next_start:
                return jsonify({"error": "Trip end time must be after start time."}), 400
            row.trip_start_at = next_start
            row.trip_end_at = next_end

        for key in allowed:
            if key in ("trip_start_at", "trip_end_at"):
                continue
            if key in payload:
                setattr(row, key, payload[key])
        if "type" in payload and row.type == "custom":
            row.type = payload["type"]

        if is_owner and "collaborators" in payload:
            next_collab_uids = _collaborator_user_ids(row.collaborators)
            removed_collab_uids = prev_collab_uids - next_collab_uids
            _sync_edit_shares_for_collaborators(
                uid, scenario_id, list(row.collaborators or []), removed_collab_uids
            )

        db.session.commit()
        if is_owner:
            return jsonify(row.to_dict())
        sh_out = ScenarioShare.query.filter_by(
            shared_with_user_id=uid, scenario_id=scenario_id
        ).first()
        owner_u = User.query.get(row.user_id)
        d_out = dict(row.to_dict())
        d_out["access"] = "shared_edit" if (sh_out and sh_out.can_edit) else "shared"
        d_out["owner_user_id"] = row.user_id
        d_out["owner_username"] = owner_u.username if owner_u else "?"
        d_out["owner_avatar"] = (
            _dicebear_avatar(owner_u.username, owner_u.avatar_style) if owner_u else None
        )
        d_out["share_recipients"] = []
        return jsonify(d_out)

    @app.delete("/api/scenarios/<scenario_id>")
    @require_auth
    def delete_scenario(scenario_id: str):
        uid = g.current_user.id
        row = Scenario.query.filter_by(user_id=uid, id=scenario_id).first()
        if not row:
            return jsonify({"error": "not found"}), 404
        if row.type != "custom":
            return jsonify({"error": "cannot delete preset"}), 400
        ScenarioShare.query.filter_by(owner_user_id=uid, scenario_id=scenario_id).delete(
            synchronize_session=False
        )
        db.session.delete(row)
        db.session.commit()
        return "", 204

    @app.get("/api/friends")
    @require_auth
    def list_friends():
        uid = g.current_user.id
        rows = (
            Friend.query.filter_by(user_id=uid)
            .filter(Friend.linked_user_id.isnot(None))
            .order_by(Friend.name)
            .all()
        )
        out: list[dict[str, Any]] = []
        for f in rows:
            u = User.query.get(f.linked_user_id)
            if u:
                dn = (u.display_name or "").strip()
                out.append(
                    {
                        "id": f.id,
                        "username": u.username,
                        "name": dn if dn else u.username,
                        "avatar": _dicebear_avatar(u.username, u.avatar_style),
                        "linked_user_id": u.id,
                        "is_registered": True,
                    }
                )
        return jsonify(out)

    @app.delete("/api/friends/<friend_id>")
    @require_auth
    def delete_friend(friend_id: str):
        uid = g.current_user.id
        row = Friend.query.filter_by(user_id=uid, id=friend_id).first()
        if not row or row.linked_user_id is None:
            return jsonify({"error": "not found"}), 404
        other = row.linked_user_id
        _cleanup_friend_from_scenarios(uid, friend_id)
        _cleanup_friend_from_scenarios(other, f"u{uid}")
        _remove_registered_friendship(uid, other)
        db.session.commit()
        return "", 204

    @app.get("/api/history")
    @require_auth
    def list_history():
        uid = g.current_user.id
        if _history_has_scenario_id_column():
            rows = (
                HistoryRecord.query.filter_by(user_id=uid)
                .order_by(HistoryRecord.id.desc())
                .all()
            )
            return jsonify([r.to_dict() for r in rows])

        # Backward-compatible fallback when DB migration has not added scenario_id yet.
        q = text(
            "SELECT id, user_id, name, date, status "
            "FROM history_records WHERE user_id=:uid ORDER BY id DESC"
        )
        rows = db.session.execute(q, {"uid": uid}).mappings().all()
        out = [
            {
                "id": int(r["id"]),
                "scenario_id": None,
                "name": r["name"],
                "date": r["date"],
                "status": r["status"],
            }
            for r in rows
        ]
        return jsonify(out)

    @app.post("/api/history")
    @require_auth
    def add_history():
        uid = g.current_user.id
        payload = request.get_json(force=True, silent=True) or {}
        name = (payload.get("name") or "").strip()
        scenario_id = str(payload.get("scenario_id") or "").strip() or None
        if not name:
            return jsonify({"error": "name required"}), 400
        now = datetime.now()
        date_str = payload.get("date") or now.strftime("%Y-%m-%d %H:%M")
        status = payload.get("status") or "completed"
        if _history_has_scenario_id_column():
            row = HistoryRecord(
                user_id=uid, scenario_id=scenario_id, name=name, date=date_str, status=status
            )
            db.session.add(row)
            db.session.commit()
            return jsonify(row.to_dict()), 201

        ins = text(
            "INSERT INTO history_records (user_id, name, date, status) "
            "VALUES (:uid, :name, :date, :status)"
        )
        db.session.execute(ins, {"uid": uid, "name": name, "date": date_str, "status": status})
        db.session.commit()
        last_id = db.session.execute(text("SELECT LAST_INSERT_ID() AS id")).mappings().first()
        new_id = int(last_id["id"]) if last_id and last_id.get("id") is not None else 0
        return jsonify({"id": new_id, "scenario_id": None, "name": name, "date": date_str, "status": status}), 201

    @app.delete("/api/history/<int:record_id>")
    @require_auth
    def delete_history_record(record_id: int):
        uid = g.current_user.id
        res = db.session.execute(
            text("DELETE FROM history_records WHERE user_id=:uid AND id=:rid"),
            {"uid": uid, "rid": record_id},
        )
        if getattr(res, "rowcount", 0) <= 0:
            return jsonify({"error": "not found"}), 404
        db.session.commit()
        return "", 204

    @app.delete("/api/history")
    @require_auth
    def clear_history():
        uid = g.current_user.id
        HistoryRecord.query.filter_by(user_id=uid).delete(synchronize_session=False)
        db.session.commit()
        return "", 204

    @app.get("/api/preferences")
    @require_auth
    def get_preferences():
        uid = g.current_user.id
        pref = AppPreference.query.filter_by(user_id=uid).first()
        if not pref:
            pref = AppPreference(user_id=uid, theme_key="cinnamon")
            db.session.add(pref)
            db.session.commit()
        return jsonify(pref.to_dict())

    @app.put("/api/preferences")
    @require_auth
    def put_preferences():
        uid = g.current_user.id
        payload = request.get_json(force=True, silent=True) or {}
        pref = AppPreference.query.filter_by(user_id=uid).first()
        if not pref:
            pref = AppPreference(user_id=uid, theme_key="cinnamon", prefs_json=None)
            db.session.add(pref)
            db.session.flush()

        theme_in = payload.get("theme_key")
        if theme_in is not None:
            t = str(theme_in).strip()
            if not t:
                return jsonify({"error": "theme_key must not be empty."}), 400
            if t not in ALLOWED_THEME_KEYS:
                return jsonify({"error": "Invalid theme_key."}), 400
            pref.theme_key = t

        pref_keys_in = [k for k in PREFERENCE_KEYS if k in payload]
        if pref_keys_in:
            merged = _normalize_prefs_blob(pref.prefs_json)
            for k in pref_keys_in:
                merged[k] = payload[k]
            pref.prefs_json = _normalize_prefs_blob(merged)

        if theme_in is None and not pref_keys_in:
            return (
                jsonify(
                    {
                        "error": "Send theme_key and/or one of: "
                        + ", ".join(sorted(PREFERENCE_KEYS))
                        + "."
                    }
                ),
                400,
            )

        db.session.commit()
        return jsonify(pref.to_dict())

    return app


def _new_id(prefix: str) -> str:
    return f"{prefix}{int(datetime.utcnow().timestamp() * 1000)}"


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
