"""Pure controller: sensor snapshots in, idempotent actuator targets out.

Only this module decides production sequence and the sorting destination.
Unity owns physical positions, grip success, exit detection and material identity.
"""

from __future__ import annotations

from collections import deque
from enum import IntEnum
import math
import uuid

from transitions import Machine


class Status(IntEnum):
    IDLE = 0
    RUNNING = 1
    PAUSED = 2
    ESTOP = 3


AXES = ("divider", "stopper", "lift", "axis1", "axis2", "hoist", "grip")
HOME = dict(zip(AXES, (1., 1., 0., 0., 0., 0., 0.)))
RECIPES = ("blue_forward", "yellow_forward", "blue_reverse", "yellow_reverse")


def classify(yellow: bool, reverse: bool) -> str:
    return "bin1" if yellow else "bin2" if reverse else "ok"


class CellController:
    def __init__(self, timeout: float = 3.0, step_timeout: float = 20.0) -> None:
        self.machine = Machine(
            model=self, states=list(Status), initial=Status.IDLE,
            auto_transitions=False, model_attribute="status", ignore_invalid_triggers=True,
            transitions=[
                {"trigger": "_start", "source": [Status.IDLE, Status.PAUSED], "dest": Status.RUNNING},
                {"trigger": "_pause", "source": Status.RUNNING, "dest": Status.PAUSED},
                {"trigger": "_estop", "source": "*", "dest": Status.ESTOP},
                {"trigger": "_release", "source": Status.ESTOP, "dest": Status.IDLE},
                {"trigger": "_reset", "source": [Status.IDLE, Status.PAUSED], "dest": Status.IDLE},
            ],
        )
        self.timeout, self.step_timeout = timeout, step_timeout
        self.inputs: dict = {}
        self.input_at = -math.inf
        self.epoch = "unbound"
        self.step = "HOME"
        self.step_elapsed = 0.0
        self.ready = False
        self.fault = "WAITING_FOR_SIMULATOR"
        self.targets = HOME.copy()
        self.motor = False
        self.feed_id = ""
        self.feed_recipe = RECIPES[0]
        self.auto_feed = True
        self.feed_queue: deque[str] = deque(maxlen=32)
        self.recipe_index = 0
        self.result = ""
        self.material_id = ""
        self.run_token = ""
        self.drop_before = 0
        self.events: deque[dict] = deque(maxlen=128)
        self.last_ui_id = ""
        self.last_note = "等待仿真连接"
        self._last_estop = False
        self._previous_at: float | None = None

    def ingest(self, inputs: dict, epoch: str, now: float) -> None:
        # All active axes must be finite normalized numbers before enabling motion.
        for key in AXES:
            value = inputs.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                return
        bool_keys = ("estop", "visible", "automatic", "carrier_present", "material_present",
                     "detect_carrier", "detect_material", "stop_carrier", "stop_material",
                     "color_yellow", "direction_reverse", "holding", "communication_hold")
        if any(type(inputs.get(key)) is not bool for key in bool_keys):
            return
        for key in ("bin1_count", "bin2_count", "ok_count", "empty_count"):
            if type(inputs.get(key)) is not int or not 0 <= inputs[key] <= 1_000_000_000:
                return
        if epoch != self.epoch:
            recovering_process = self.epoch == "unbound" and (inputs["carrier_present"] or inputs["holding"])
            self.epoch = epoch
            self._estop() if inputs["estop"] else self._reset_to_idle()
            self._clear_process()
            self._last_estop = inputs["estop"]
            if recovering_process and not inputs["estop"]:
                # A new Python process cannot infer an interrupted pickup from positions alone.
                self._start()
                self._pause()
                self.fault = "RECOVERY_RESET_REQUIRED"
                self.last_note = "控制器已重启，在制物料需要复位清理"
        self.inputs = inputs.copy()
        self.input_at = now

    def _reset_to_idle(self) -> None:
        if self.status == Status.ESTOP:
            self._release()
        if self.status == Status.RUNNING:
            self._pause()
        self._reset()

    def _clear_process(self) -> None:
        self.step, self.step_elapsed = "HOME", 0.0
        self.ready = False
        self.targets, self.motor = HOME.copy(), False
        self.feed_id = self.result = self.material_id = self.run_token = ""
        self.feed_queue.clear()
        self.events.clear()
        self.fault = ""

    def event(self, event: dict) -> None:
        self.events.append(event)

    def pause(self) -> None:
        if self.status == Status.RUNNING:
            self._pause()

    def at(self, **targets: float) -> bool:
        return all(abs(self.inputs.get(k, -100) - v) <= .015 for k, v in targets.items())

    def move_step(self, step: str) -> None:
        self.step, self.step_elapsed = step, 0.0

    def tick(self, now: float) -> dict:
        dt = 0.0 if self._previous_at is None else max(0.0, min(now - self._previous_at, .25))
        self._previous_at = now
        comm_ok = now - self.input_at <= self.timeout
        events = list(self.events)
        self.events.clear()
        estop = self.inputs.get("estop", False) or any(e.get("action") == "estop" for e in events)
        automatic = self.inputs.get("automatic", True)
        visible = self.inputs.get("visible", False)
        pause_requested = any(e.get("action") in ("stop", "hidden") for e in events)
        if estop:
            if self.status != Status.ESTOP:
                self._estop()
                self._clear_process()
            self._last_estop = True
        elif self.status == Status.ESTOP and self._last_estop and comm_ok:
            self._release()
            self._clear_process()
            self._last_estop = False

        if not comm_ok or not visible or pause_requested or not automatic:
            self.pause()
        if not comm_ok:
            self.fault = "SIMULATOR_TIMEOUT"
        elif not visible:
            self.fault = "BROWSER_HIDDEN"
        elif self.fault in ("SIMULATOR_TIMEOUT", "BROWSER_HIDDEN", "WAITING_FOR_SIMULATOR"):
            self.fault = ""
        if self.inputs.get("device_fault"):
            self.fault = "DEVICE:" + str(self.inputs["device_fault"])
            self.pause()
        if (self.status == Status.RUNNING and self.inputs.get("communication_hold")
                and self.run_token and self.inputs.get("run_token_seen") == self.run_token):
            self.pause()

        for event in events:
            action = event.get("action")
            self.last_ui_id = event.get("id", "")
            if action == "auto_feed":
                self.auto_feed = bool(event.get("value"))
            elif action == "feed" and self.status != Status.ESTOP:
                recipe = event.get("recipe", "blue_forward")
                if recipe in (*RECIPES, "empty"):
                    self.feed_queue.append(recipe)
            elif action == "start":
                if comm_ok and visible and automatic and self.ready and not estop and not pause_requested and not self.fault:
                    self.run_token = event.get("id") or uuid.uuid4().hex
                    self._start()
                    self.last_note = "自动运行"
                else:
                    self.last_note = "启动未接受：检查自动模式、初始化和故障"

        if self.status == Status.ESTOP:
            self.motor = False
            self.ready = False
        elif self.status == Status.IDLE and comm_ok and visible:
            self.targets = HOME.copy()
            self.motor = False
            if self.at(**HOME):
                self.ready = True
                if self.step == "HOME":
                    self.move_step("WAIT_CARRIER")
                self.last_note = "初始化完成，等待启动"
            else:
                self.step_elapsed += dt
                if self.step_elapsed > self.step_timeout:
                    self.fault = "HOME_TIMEOUT"
        elif self.status == Status.RUNNING:
            self.step_elapsed += dt
            self._sequence()
            if self.step not in ("WAIT_CARRIER",) and self.step_elapsed > self.step_timeout:
                self.fault = f"STEP_TIMEOUT:{self.step}"
                self._pause()
                self.last_note = "到位超时：排除故障后复位"

        moving = comm_ok and visible and not self.fault and self.status in (Status.IDLE, Status.RUNNING)
        return {
            "status": int(self.status), "step": self.step, "ready": self.ready,
            "fault": self.fault, "note": self.last_note, "motion_allowed": moving,
            "motor": self.motor and self.status == Status.RUNNING and moving,
            **self.targets, "feed_id": self.feed_id, "feed_recipe": self.feed_recipe,
            "run_token": self.run_token, "ui_ack": self.last_ui_id,
            "auto_feed": self.auto_feed, "queued": len(self.feed_queue),
            "result": self.result, "material_id": self.material_id,
            "step_elapsed": round(self.step_elapsed, 3),
        }

    def _sequence(self) -> None:
        i, t, step = self.inputs, self.targets, self.step
        self.motor = step in ("WAIT_CARRIER", "DETECT", "APPROACH", "RELEASE", "RELEASE_DELAY")
        if step == "WAIT_CARRIER":
            t.update(HOME)
            t["divider"] = 0.
            if i["carrier_present"]:
                self.move_step("DETECT")
            elif self.feed_queue or self.auto_feed:
                self.feed_recipe = self.feed_queue.popleft() if self.feed_queue else RECIPES[self.recipe_index % 4]
                self.recipe_index += 1
                self.feed_id = uuid.uuid4().hex
                self.move_step("DETECT")
        elif step == "DETECT":
            if i["detect_carrier"]:
                self.result = classify(i["color_yellow"], i["direction_reverse"]) if i["detect_material"] else "empty"
                self.material_id = i.get("material_id", "")
                t["divider"] = 1.
                self.move_step("APPROACH")
        elif step == "APPROACH" and i["stop_carrier"]:
            self.motor = False
            self.move_step("LIFT" if self.result in ("bin1", "bin2") else "RELEASE")
        elif step == "LIFT":
            t["lift"] = 1.
            if self.at(lift=1., hoist=0., axis1=0., axis2=0.):
                self.move_step("PICK_DOWN")
        elif step == "PICK_DOWN":
            t["hoist"] = 1.
            if self.at(hoist=1.):
                self.move_step("GRIP")
        elif step == "GRIP":
            t["grip"] = 1.
            if self.at(grip=1.) and i["holding"]:
                self.move_step("PICK_UP")
        elif step == "PICK_UP":
            t["hoist"] = 0.
            if self.at(hoist=0.):
                self.move_step("TRAVEL")
        elif step == "TRAVEL":
            t["axis1"], t["axis2"] = 1., float(self.result == "bin2")
            if self.at(axis1=t["axis1"], axis2=t["axis2"], hoist=0.):
                self.drop_before = i[self.result + "_count"]
                self.move_step("DROP_DOWN")
        elif step == "DROP_DOWN":
            t["hoist"] = 1.
            if self.at(hoist=1.):
                self.move_step("UNGRIP")
        elif step == "UNGRIP":
            t["grip"] = 0.
            if self.at(grip=0.) and not i["holding"] and i[self.result + "_count"] == self.drop_before + 1:
                self.move_step("DROP_UP")
        elif step == "DROP_UP":
            t["hoist"] = 0.
            if self.at(hoist=0.):
                self.move_step("RETURN")
        elif step == "RETURN":
            t["axis1"] = t["axis2"] = 0.
            if self.at(axis1=0., axis2=0., hoist=0.):
                self.move_step("LOWER")
        elif step == "LOWER":
            t["lift"] = 0.
            if self.at(lift=0.):
                self.move_step("RELEASE")
        elif step == "RELEASE":
            t["stopper"] = 0.
            if self.at(stopper=0.):
                self.move_step("RELEASE_DELAY")
        elif step == "RELEASE_DELAY":
            # Screenshot 160 shows step 11: delay 10 seconds after stopper retraction.
            # The carrier must also have left; elapsed time alone cannot reset the stop.
            if self.step_elapsed >= 10.0 and not i["carrier_present"]:
                self.motor = False
                self.feed_id = self.result = self.material_id = ""
                self.move_step("RESET_STOP")
        elif step == "RESET_STOP":
            t["stopper"] = 1.
            if self.at(stopper=1.):
                self.move_step("WAIT_CARRIER")
