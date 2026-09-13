import json

import pytest

from controller.protocol import EnvelopeWriter, ReplayGuard, decode, topic_prefix


def test_duplicate_and_out_of_order_commands_are_rejected():
    w, guard = EnvelopeWriter("test-session", "simulator"), ReplayGuard()
    older, newer = w.make("one", {}), w.make("one", {})
    assert guard.accept("device/inputs", newer)
    assert not guard.accept("device/inputs", older)
    assert not guard.accept("device/inputs", newer)
    assert guard.accept("ui/events", older)


@pytest.mark.parametrize("age", [3001, -5001])
def test_expired_or_future_packets(age):
    msg = EnvelopeWriter("test-session", "simulator").make("epoch", {}, now_ms=10000)
    with pytest.raises(ValueError):
        decode(json.dumps(msg), "test-session", now_ms=10000 + age)


def test_topic_is_session_scoped():
    assert topic_prefix("abcdefgh") == "brics2026/abcdefgh/cell01/"
    for name in ("#", "abc/+/abc", "short"):
        with pytest.raises(ValueError):
            topic_prefix(name)
