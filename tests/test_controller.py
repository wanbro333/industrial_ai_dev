import math

import pytest

from controller.core import Status, classify, CellController


def start(cell, now=0.05):
    cell.event({"action": "start", "id": "new-start"})
    return cell.tick(now)


@pytest.mark.parametrize("yellow,reverse,result", [(False, False, "ok"), (True, False, "bin1"),
                                                  (False, True, "bin2"), (True, True, "bin1")])
def test_sorting_truth_table(yellow, reverse, result):
    assert classify(yellow, reverse) == result


def test_four_states_and_release_does_not_restart(cell, inputs):
    assert cell.status == Status.IDLE and cell.ready
    assert start(cell)["status"] == 1
    cell.event({"action": "stop"})
    assert cell.tick(.1)["status"] == 2
    assert start(cell, .2)["status"] == 1
    cell.ingest({**inputs, "estop": True}, "estop-epoch", .3)
    assert cell.tick(.3)["status"] == 3
    cell.ingest(inputs, "release-epoch", .4)
    assert cell.tick(.4)["status"] == 0
    assert not cell.tick(.5)["motor"]


def test_priority_stop_and_estop_dominate_start(cell, inputs):
    start(cell)
    cell.event({"action": "start"})
    cell.event({"action": "stop"})
    assert cell.tick(.1)["status"] == 2
    cell.event({"action": "start"})
    cell.event({"action": "estop"})
    assert cell.tick(.2)["status"] == 3


def test_manual_selector_prevents_start(cell, inputs):
    cell.ingest({**inputs, "automatic": False}, cell.epoch, .1)
    assert start(cell, .1)["status"] == 0


def test_pause_preserves_step_targets_and_elapsed_time(cell, inputs):
    start(cell)
    cell.move_step("GRIP")
    cell.targets["grip"] = 1.
    cell.event({"action": "stop"})
    before = cell.tick(.1)
    for n in range(1, 51):
        cell.ingest(inputs, cell.epoch, n / 10)
        after = cell.tick(n / 10)
    assert after["status"] == 2
    assert after["step"] == before["step"] == "GRIP"
    assert after["step_elapsed"] == before["step_elapsed"]
    assert after["grip"] == 1. and not after["motion_allowed"]


def test_watchdog_and_reconnect_need_new_start(cell, inputs):
    start(cell)
    assert cell.tick(4)["status"] == 2
    cell.ingest(inputs, cell.epoch, 4.1)
    assert cell.tick(4.1)["status"] == 2
    assert start(cell, 4.2)["status"] == 1


def test_bad_snapshot_does_not_refresh_watchdog(cell, inputs):
    for bad in (math.nan, math.inf, "0", -1, True):
        cell.ingest({**inputs, "lift": bad}, cell.epoch, 5)
    assert cell.input_at == 0


def test_ack_alone_cannot_complete_grip(cell, inputs):
    start(cell)
    cell.move_step("GRIP")
    cell.ingest({**inputs, "grip": 1.}, cell.epoch, .2)
    assert cell.tick(.2)["step"] == "GRIP"
    cell.ingest({**inputs, "grip": 1., "holding": True}, cell.epoch, .3)
    assert cell.tick(.3)["step"] == "PICK_UP"


def test_missing_arrival_times_out_without_advancing(cell, inputs):
    start(cell)
    cell.move_step("LIFT")
    for n in range(1, 450):
        now = n * .05
        cell.ingest(inputs, cell.epoch, now)
        output = cell.tick(now)
    assert output["status"] == 2 and output["step"] == "LIFT"
    assert output["fault"] == "STEP_TIMEOUT:LIFT"
    assert start(cell, 22.5)["status"] == 2


def test_new_scene_clears_inflight_and_stays_idle(cell, inputs):
    start(cell)
    assert cell.feed_id
    cell.ingest(inputs, "new-epoch", .3)
    output = cell.tick(.3)
    assert output["status"] == 0 and output["feed_id"] == "" and output["run_token"] == ""


def test_initialization_requires_actual_stop_and_lift(cell, inputs):
    cell.ingest({**inputs, "stopper": 0., "lift": 1.}, "new", .1)
    output = start(cell, .1)
    assert output["status"] == 0 and not output["ready"]
    assert output["stopper"] == 1. and output["lift"] == 0.
    assert output["motion_allowed"] and not output["motor"]


def test_controller_restart_with_workpiece_requires_reset(inputs):
    c = CellController()
    c.ingest({**inputs, "holding": True, "carrier_present": True, "hoist": .6}, "existing-scene", 0)
    output = c.tick(0)
    assert output["status"] == 2 and not output["motion_allowed"]
    assert output["fault"] == "RECOVERY_RESET_REQUIRED"


def test_release_requires_ten_running_seconds_and_carrier_exit(cell, inputs):
    start(cell)
    cell.auto_feed = False
    cell.move_step("RELEASE")
    snapshot = {**inputs, "stopper": 0., "communication_hold": False, "carrier_present": True}
    cell.ingest(snapshot, cell.epoch, .1)
    assert cell.tick(.1)["step"] == "RELEASE_DELAY"
    for n in range(1, 151):
        now = .1 + n * .05
        cell.ingest(snapshot, cell.epoch, now)
        assert cell.tick(now)["step"] == "RELEASE_DELAY"
    cell.event({"action": "stop"})
    paused = cell.tick(7.7)["step_elapsed"]
    for n in range(1, 101):
        now = 7.7 + n * .05
        cell.ingest(snapshot, cell.epoch, now)
        assert cell.tick(now)["step_elapsed"] == paused
    start(cell, 12.75)
    for n in range(1, 61):
        now = 12.75 + n * .05
        cell.ingest(snapshot, cell.epoch, now)
        assert cell.tick(now)["step"] == "RELEASE_DELAY", "A carrier still on the belt blocks reset"
    cell.ingest({**snapshot, "carrier_present": False}, cell.epoch, 15.8)
    assert cell.tick(15.8)["step"] == "RESET_STOP"
