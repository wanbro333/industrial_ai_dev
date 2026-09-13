"""The shared v1 envelope. No retained commands or accumulated motion deltas."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field

SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
MAX_BYTES = 32_768


def topic_prefix(session: str) -> str:
    if not SESSION_RE.fullmatch(session):
        raise ValueError("session must contain 8–64 letters, digits, underscores or hyphens")
    return f"brics2026/{session}/cell01/"


@dataclass
class EnvelopeWriter:
    session: str
    sender: str
    peer: str = field(default_factory=lambda: uuid.uuid4().hex)
    seq: int = 0

    def make(self, epoch: str, data: dict, now_ms: int | None = None) -> dict:
        self.seq += 1
        return {
            "v": 1, "session": self.session, "epoch": epoch,
            "sender": self.sender, "peer": self.peer, "seq": self.seq,
            "id": f"{self.peer}:{self.seq}",
            "sent_ms": int(time.time() * 1000) if now_ms is None else now_ms,
            "ttl_ms": 3000, "data": data,
        }


def decode(raw: bytes | str, session: str, now_ms: int | None = None) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized message")
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(msg, dict) or msg.get("v") != 1 or msg.get("session") != session:
        raise ValueError("wrong version or session")
    for name in ("epoch", "peer", "id", "sender"):
        if not isinstance(msg.get(name), str) or not 1 <= len(msg[name]) <= 128:
            raise ValueError(f"invalid {name}")
    for name in ("seq", "sent_ms", "ttl_ms"):
        if type(msg.get(name)) is not int:
            raise ValueError(f"invalid {name}")
    if msg["seq"] < 1 or not 1 <= msg["ttl_ms"] <= 5000:
        raise ValueError("invalid sequence or TTL")
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    age = now_ms - msg["sent_ms"]
    if age > msg["ttl_ms"] or age < -5000:
        raise ValueError("expired message or excessive clock skew")
    if not isinstance(msg.get("data"), dict):
        raise ValueError("data must be an object")
    return msg


class ReplayGuard:
    """Monotonic sequence per peer, epoch and stream; bounded memory."""

    def __init__(self) -> None:
        self.seen: dict[tuple[str, str, str], int] = {}

    def accept(self, stream: str, msg: dict) -> bool:
        key = msg["peer"], msg["epoch"], stream
        if msg["seq"] <= self.seen.get(key, 0):
            return False
        if key not in self.seen and len(self.seen) >= 64:
            self.seen.pop(next(iter(self.seen)))
        self.seen[key] = msg["seq"]
        return True
