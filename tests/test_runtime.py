import json

from controller.main import Runtime
from controller.protocol import EnvelopeWriter


def send(runtime, writer, inputs, now, epoch="scene-a", retained=False):
    runtime.process("device/inputs", json.dumps(writer.make(epoch, inputs)).encode(), retained, now)


def test_retained_or_invalid_input_cannot_bind_peer(inputs):
    runtime, writer = Runtime("test-session"), EnvelopeWriter("test-session", "simulator")
    send(runtime, writer, inputs, 1, retained=True)
    assert runtime.sim_peer == ""
    send(runtime, writer, {"divider": 0}, 1)
    assert runtime.sim_peer == ""
    send(runtime, writer, inputs, 1)
    assert runtime.sim_peer == writer.peer


def test_scene_rollover_rejects_older_epoch_even_with_new_sequence(inputs):
    runtime, writer = Runtime("test-session"), EnvelopeWriter("test-session", "simulator")
    send(runtime, writer, inputs, 1)
    send(runtime, writer, inputs, 2, epoch="scene-b")
    send(runtime, writer, {**inputs, "estop": True}, 3, epoch="scene-a")
    assert runtime.core.epoch == "scene-b" and not runtime.core.inputs["estop"]


def test_invalid_new_peer_after_timeout_does_not_retire_valid_scene(inputs):
    runtime, first, second = Runtime("test-session"), EnvelopeWriter("test-session", "simulator"), EnvelopeWriter("test-session", "simulator")
    send(runtime, first, inputs, 1)
    send(runtime, second, {}, 5, epoch="new-scene")
    send(runtime, first, inputs, 6)
    assert runtime.core.input_at == 6 and runtime.sim_peer == first.peer


def test_only_one_live_simulator_and_new_instance_needs_new_epoch(inputs):
    runtime, first, second = Runtime("test-session"), EnvelopeWriter("test-session", "simulator"), EnvelopeWriter("test-session", "simulator")
    send(runtime, first, inputs, 1)
    send(runtime, second, inputs, 2, epoch="new-scene")
    assert runtime.sim_peer == first.peer
    send(runtime, second, inputs, 5)
    assert runtime.sim_peer == first.peer
    send(runtime, second, inputs, 5, epoch="new-scene")
    assert runtime.sim_peer == second.peer


def test_button_event_is_accepted_once(inputs):
    runtime, writer = Runtime("test-session"), EnvelopeWriter("test-session", "simulator")
    send(runtime, writer, inputs, 1)
    event = json.dumps(writer.make("scene-a", {"action": "feed", "recipe": "blue_forward"})).encode()
    runtime.process("ui/events", event, False, 1)
    runtime.process("ui/events", event, False, 1)
    assert len(runtime.core.events) == 1
