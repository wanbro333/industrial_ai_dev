"""MQTT runtime. Callbacks enqueue; a single 20 Hz loop owns all control state."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import queue
import threading
import time
import uuid

import paho.mqtt.client as mqtt

from .core import CellController
from .protocol import EnvelopeWriter, ReplayGuard, decode, topic_prefix

LOG = logging.getLogger("cell")


class Runtime:
    def __init__(self, session: str, broker: str = "broker.emqx.io", port: int = 1883) -> None:
        self.prefix = topic_prefix(session)
        self.session, self.broker, self.port = session, broker, port
        self.writer = EnvelopeWriter(session, "controller")
        self.core = CellController()
        self.guard = ReplayGuard()
        self.inbox: queue.Queue = queue.Queue(maxsize=512)
        self.connected = threading.Event()
        self.sim_peer = ""
        self.retired_epochs: set[str] = set()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="ctrl-" + self.writer.peer, clean_session=True)
        self.client.max_queued_messages_set(4)
        self.client.max_inflight_messages_set(4)
        self.client.reconnect_delay_set(1, 10)
        self.client.on_connect = self._connect
        self.client.on_disconnect = self._disconnect
        self.client.on_message = self._message
        self.client.will_set(self.prefix + "health/controller", json.dumps({"online": False}), qos=1, retain=False)
        self.rejected = 0
        self.applied_ack = ""

    def _connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            LOG.error("Broker rejected connection: %s", reason_code)
            return
        client.subscribe([(self.prefix + stream, 1) for stream in ("device/inputs", "ui/events", "device/ack")])
        self.connected.set()
        LOG.info("MQTT connected: %s:%s, session=%s", self.broker, self.port, self.session)

    def _disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self.connected.clear()
        self._enqueue(("_disconnect", None, False))

    def _enqueue(self, message) -> None:
        try:
            self.inbox.put_nowait(message)
        except queue.Full:
            # Backpressure is a fault: never discard an emergency and keep moving.
            self.connected.clear()

    def _message(self, client, userdata, message) -> None:
        if len(message.payload) <= 32768:
            self._enqueue((message.topic.removeprefix(self.prefix), message.payload, message.retain))

    def process(self, stream: str, raw: bytes, retained: bool, now: float) -> None:
        if stream == "_disconnect":
            self.core.input_at = -float("inf")
            self.core._pause()
            return
        if retained:
            self.rejected += 1
            return
        try:
            msg = decode(raw, self.session)
        except ValueError:
            self.rejected += 1
            return
        if msg["sender"] != "simulator" or msg["epoch"] in self.retired_epochs:
            self.rejected += 1
            return
        if stream == "device/inputs":
            if self.sim_peer and self.sim_peer != msg["peer"]:
                if now - self.core.input_at <= self.core.timeout or msg["epoch"] == self.core.epoch:
                    self.rejected += 1
                    return
            if not self.guard.accept(stream, msg):
                return
            previous_epoch = self.core.epoch
            self.core.ingest(msg["data"], msg["epoch"], now)
            if self.core.input_at != now:
                self.rejected += 1
                return
            self.sim_peer = msg["peer"]
            if previous_epoch not in ("unbound", msg["epoch"]):
                self.retired_epochs.add(previous_epoch)
        elif msg["peer"] == self.sim_peer and msg["epoch"] == self.core.epoch and self.guard.accept(stream, msg):
            if stream == "ui/events":
                self.core.event({**msg["data"], "id": msg["id"]})
            elif stream == "device/ack":
                self.applied_ack = str(msg["data"].get("command_id", ""))

    def run(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        self.client.connect_async(self.broker, self.port, keepalive=10)
        self.client.loop_start()
        last_publish = last_heartbeat = 0.0
        previous = None
        try:
            while not stop.is_set():
                now = time.monotonic()
                for _ in range(512):
                    try:
                        message = self.inbox.get_nowait()
                    except queue.Empty:
                        break
                    self.process(*message, now)
                if not self.connected.is_set():
                    self.core.input_at = -float("inf")
                output = self.core.tick(now)
                summary = output["status"], output["step"], output["fault"]
                changed = summary != previous
                if changed:
                    LOG.info("Status=%s step=%s fault=%s", *summary)
                    previous = summary
                if self.connected.is_set() and self.core.epoch != "unbound":
                    if changed or now - last_publish >= .1:
                        msg = self.writer.make(self.core.epoch, output)
                        # No application-level offline queue; stale retransmissions are rejected by TTL/epoch.
                        self.client.publish(self.prefix + "control/outputs", json.dumps(msg), qos=1, retain=False)
                        last_publish = now
                    if now - last_heartbeat >= 1:
                        self.client.publish(self.prefix + "health/controller", json.dumps(
                            self.writer.make(self.core.epoch, {"online": True, "rejected": self.rejected})), qos=0, retain=False)
                        last_heartbeat = now
                stop.wait(max(0., .05 - (time.monotonic() - now)))
        finally:
            self.client.disconnect()
            self.client.loop_stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Python controller for the Unity WebGL industrial cell")
    parser.add_argument("--session", help="same session shown in the browser; generated when omitted")
    parser.add_argument("--broker", default="broker.emqx.io")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--web-port", type=int, default=8765)
    args = parser.parse_args()
    session = args.session or uuid.uuid4().hex[:16]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("transitions").setLevel(logging.WARNING)
    runtime = Runtime(session, args.broker, args.port)
    Path("runtime").mkdir(exist_ok=True)
    Path("runtime/session.json").write_text(json.dumps({"session": session}, indent=2), encoding="utf8")
    print(f"Open http://localhost:{args.web_port}/?session={session}", flush=True)
    try:
        runtime.run()
    except KeyboardInterrupt:
        print("Controller stopped. The simulator will freeze on watchdog timeout.")


if __name__ == "__main__":
    main()
