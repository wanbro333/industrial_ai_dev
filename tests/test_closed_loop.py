"""Runs the *same C# device model shipped in Unity* against the Python controller.

Build tests/device_harness once using scripts/test.ps1. This is functional simulation
testing, not a substitute for the WebGL/WSS browser acceptance run.
"""
import json
from pathlib import Path
import subprocess

import pytest

from controller.core import CellController

HARNESS = Path(__file__).parent / "device_harness/bin/Release/net8.0/DeviceHarness.dll"


@pytest.fixture
def loop():
    if not HARNESS.exists():
        pytest.skip("Build the C# device harness using scripts/test.ps1")
    proc = subprocess.Popen(["dotnet", str(HARNESS)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, encoding="utf8")
    c = CellController()
    c.auto_feed = False
    now = 0.

    def exchange(action=None, **extra):
        nonlocal now
        now += .05
        start_ids = [e.get("id") for e in c.events if e.get("action") == "start"]
        req = {"outputs": c.tick(now), "dt": .05, "t": now, **extra}
        if start_ids:
            req["authorize"] = start_ids[-1]
        if action:
            req["action"] = action
            # Emergency/reset act locally first, before remote old-epoch outputs.
            req.pop("outputs")
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        response = json.loads(proc.stdout.readline())
        c.ingest(response["inputs"], response["epoch"], now)
        return response
    exchange()
    exchange()
    yield c, exchange
    proc.stdin.close()
    proc.wait(timeout=5)


@pytest.mark.parametrize("recipe,expected", [("blue_forward", (1, 0, 0, 0)),
    ("yellow_forward", (0, 1, 0, 0)), ("blue_reverse", (0, 0, 1, 0)),
    ("yellow_reverse", (0, 1, 0, 0)), ("empty", (0, 0, 0, 1))])
def test_real_device_motion_and_sorting(loop, recipe, expected):
    c, exchange = loop
    c.event({"action": "feed", "recipe": recipe})
    c.event({"action": "start", "id": "start-1"})
    visited = set()
    for _ in range(1800):
        r = exchange()
        visited.add(c.step)
        if any(r["inputs"][key] for key in ("ok_count", "bin1_count", "bin2_count", "empty_count")) and c.step == "WAIT_CARRIER":
            break
    i = r["inputs"]
    assert not c.fault, (c.fault, c.step, i)
    assert tuple(i[key] for key in ("ok_count", "bin1_count", "bin2_count", "empty_count")) == expected
    assert not i["carrier_present"] and not i["holding"]
    if "yellow" in recipe or recipe == "blue_reverse":
        assert {"GRIP", "TRAVEL", "UNGRIP", "RETURN"} <= visited
    for _ in range(60):
        r = exchange()
    assert tuple(r["inputs"][key] for key in ("ok_count", "bin1_count", "bin2_count", "empty_count")) == expected


def test_pause_while_holding_and_estop_clear_held_material(loop):
    c, exchange = loop
    c.event({"action": "feed", "recipe": "yellow_reverse"})
    c.event({"action": "start", "id": "start-1"})
    for _ in range(1000):
        r = exchange()
        if r["inputs"]["holding"]:
            break
    assert r["inputs"]["holding"]
    c.event({"action": "stop"})
    before = exchange()["inputs"]
    for _ in range(100):
        after = exchange()["inputs"]
    assert after["holding"] and after["hoist"] == before["hoist"] and after["axis1"] == before["axis1"]
    r = exchange("estop")
    assert r["material_count"] == 0 and not r["inputs"]["carrier_present"]
    assert c.tick(10)["status"] == 3
    r = exchange("release")
    assert c.tick(10.1)["status"] == 0


def test_stuck_lift_stops_sequence(loop):
    c, exchange = loop
    c.event({"action": "feed", "recipe": "blue_reverse"})
    c.event({"action": "start", "id": "start-1"})
    for _ in range(900):
        r = exchange(jam="lift")
        if c.fault:
            break
    assert c.fault == "STEP_TIMEOUT:LIFT"
    assert not r["inputs"]["holding"] and r["inputs"]["lift"] == 0


def test_late_start_packet_cannot_release_local_stop(loop):
    c, exchange = loop
    c.event({"action": "feed", "recipe": "blue_forward"})
    c.event({"action": "start", "id": "first-start"})
    for _ in range(20):
        exchange()
    delayed = c.tick(1.2).copy()
    before = exchange("hold")["inputs"]
    delayed["run_token"] = "an-earlier-start-that-arrived-late"
    for _ in range(30):
        after = exchange(outputs=delayed)["inputs"]
    assert after["communication_hold"]
    assert after["carrier_x"] == before["carrier_x"]


def test_new_user_start_continues_after_local_hold(loop):
    c, exchange = loop
    c.event({"action": "feed", "recipe": "blue_forward"})
    c.event({"action": "start", "id": "first-start"})
    for _ in range(20):
        exchange()
    before = exchange("hold")["inputs"]
    for _ in range(10):
        exchange()
    assert c.status == 2
    c.event({"action": "start", "id": "explicit-resume"})
    for _ in range(20):
        after = exchange()["inputs"]
    assert not after["communication_hold"] and after["carrier_x"] > before["carrier_x"]


def test_continuous_mixed_feed_completes_all_four_recipes_once(loop):
    c, exchange = loop
    c.auto_feed = True
    c.event({"action": "start", "id": "continuous-start"})
    for _ in range(5000):
        r = exchange()
        i = r["inputs"]
        if i["ok_count"] + i["bin1_count"] + i["bin2_count"] == 4:
            c.auto_feed = False
        if c.step == "WAIT_CARRIER" and not c.auto_feed:
            break
    assert not c.fault
    assert (i["ok_count"], i["bin1_count"], i["bin2_count"]) == (1, 2, 1)
    assert not i["carrier_present"] and not i["holding"]
