import mqtt from 'mqtt';
import { Protocol, validSession } from './protocol.js';

export class CellBridge {
  constructor(view) {
    this.view = view;
    const url = new URL(location.href);
    const configured = url.searchParams.get('session');
    const session = validSession(configured) ? configured : crypto.randomUUID().replaceAll('-', '').slice(0, 16);
    url.searchParams.set('session', session);
    history.replaceState({}, '', url);
    this.protocol = new Protocol(session);
    this.prefix = `brics2026/${session}/cell01/`;
    this.unity = null;
    this.object = null;
    this.client = null;
    this.inputs = null;
    this.outputs = null;
    this.controllerAt = -Infinity;
    this.connected = false;
    this.sent = 0;
    this.received = 0;
    this.rejected = 0;
    this.lastAckAt = -Infinity;
    this.pendingUi = null;
    this.actionAfter = 0;
    this.view.session(session);
    document.addEventListener('visibilitychange', () => this.call('OnVisibility', document.hidden ? 'hidden' : 'visible'));
    document.addEventListener('freeze', () => this.call('OnVisibility', 'hidden'));
    document.addEventListener('resume', () => this.call('OnVisibility', document.hidden ? 'hidden' : 'visible'));
    window.addEventListener('pagehide', () => this.client?.end(true));
  }
  setUnity(instance) { this.unity = instance; this.connectIfReady(); }
  bind(name) { this.object = name; this.connectIfReady(); }
  call(method, value) { if (this.unity && this.object) this.unity.SendMessage(this.object, method, value); }
  connectIfReady() {
    if (!this.unity || !this.object || this.client) return;
    this.call('OnVisibility', document.hidden ? 'hidden' : 'visible');
    this.client = mqtt.connect('wss://broker.emqx.io:8084/mqtt', {
      clientId: `sim-${this.protocol.peer}`, clean: true, protocolVersion: 5,
      keepalive: 10, connectTimeout: 10000, reconnectPeriod: 1500,
      queueQoSZero: false, resubscribe: true,
      will: { topic: this.prefix + 'health/simulator', payload: JSON.stringify({ online: false }), qos: 0, retain: false },
    });
    this.client.on('connect', () => {
      this.connected = true;
      this.client.subscribe(this.prefix + 'control/outputs', { qos: 1 });
      this.call('OnConnection', 'connected');
      this.view.log('MQTT 已连接，等待控制器同步');
    });
    this.client.on('close', () => { this.connected = false; this.call('OnConnection', 'disconnected'); });
    this.client.on('error', error => this.view.log(`连接提示：${error.message}`));
    this.client.on('message', (topic, payload, packet) => {
      if (topic !== this.prefix + 'control/outputs') return;
      const previousPeer = this.protocol.controller;
      const msg = this.protocol.accept(payload.toString(), packet.retain);
      if (!msg) { this.rejected += 1; return; }
      // A resumed browser can deliver fresh MQTT callbacks before Unity's next Tick.
      // Latch the reception gap here so that callback ordering cannot resume motion.
      if (performance.now() - this.controllerAt > 3000) this.call('OnControllerChanged', 'controller-timeout');
      if (previousPeer && previousPeer !== msg.peer) this.call('OnControllerChanged', 'changed');
      this.received += 1;
      this.controllerAt = performance.now();
      this.outputs = msg.data;
      if (this.pendingUi?.id === msg.data.ui_ack) this.pendingUi = null;
      this.call('OnOutputs', JSON.stringify(msg));
    });
  }
  publish(stream, data) {
    if (!this.connected || !this.client?.connected || !this.protocol.epoch) return null;
    const msg = this.protocol.make(data);
    this.client.publish(this.prefix + stream, JSON.stringify(msg), {
      qos: 1, retain: false, properties: { messageExpiryInterval: 3 },
    }, error => {
      if (!error || stream !== 'ui/events') return;
      if (this.pendingUi?.id === msg.id) this.pendingUi = null;
      this.view.log(`操作发送失败，请重试：${error.message}`);
      if (data.action === 'start') this.call('OnControllerChanged', 'publish-rejected');
    });
    this.sent += 1;
    return msg.id;
  }
  telemetry(json, epoch) {
    const inputs = JSON.parse(json);
    this.inputs = inputs;
    if (this.protocol.epoch !== epoch) {
      this.protocol.epoch = epoch;
      this.outputs = null;
      this.view.log('场景已同步，旧代次指令失效');
    }
    this.publish('device/inputs', inputs);
    this.view.render(this);
  }
  sendEvent(json) {
    const event = JSON.parse(json);
    const id = this.publish('ui/events', event);
    this.lastUiEvent = { action: event.action, id, connected: this.connected, at: Date.now() };
    if (id) this.pendingUi = { id, action: event.action, until: performance.now() + 3000 };
    // Called from a Unity .jslib callback: do not re-enter the WASM runtime on its current stack.
    if (event.action === 'start' && id) queueMicrotask(() => this.call('OnStartToken', id));
    return id;
  }
  ack(json) {
    // Acknowledgement is diagnostic; sensor feedback drives the controller.
    // Avoid echoing every output on the public broker's limited message quota.
    if (performance.now() - this.lastAckAt < 2000) return;
    this.lastAckAt = performance.now();
    this.publish('device/ack', JSON.parse(json));
  }
  act(action, value = false, recipe = '') {
    const immediate = action === 'stop' || action === 'estop' || (action === 'mode' && !value);
    if (!immediate && action !== 'camera' && this.uiBusy()) return;
    if (action !== 'camera') this.actionAfter = performance.now() + 500;
    this.lastUiAction = action;
    this.call('OnUiEvent', JSON.stringify({ action, value, recipe }));
    this.view.render(this);
  }
  uiBusy() {
    if (this.pendingUi && performance.now() > this.pendingUi.until) {
      this.view.log('控制器未确认操作，请重试。');
      if (this.pendingUi.action === 'start') this.call('OnControllerChanged', 'ui-timeout');
      this.pendingUi = null;
    }
    return !!this.pendingUi || performance.now() < this.actionAfter;
  }
}
