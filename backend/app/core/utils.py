from __future__ import annotations
import re
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


def public(doc: dict | None) -> dict | None:
    """Rename Mongo `_id` to `id` for API responses."""
    if doc is None:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = d.pop("_id")
    return d


def public_list(docs) -> list[dict]:
    return [public(d) for d in docs]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def strip_json_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


def deep_get(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur
