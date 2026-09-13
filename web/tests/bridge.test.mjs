import test from 'node:test';
import assert from 'node:assert/strict';
import { CellBridge } from '../src/bridge.js';

function fixture(t) {
  let now = 0;
  t.mock.method(performance, 'now', () => now);
  const listeners = {}, calls = [], sent = [], logs = [];
  globalThis.location = { href: 'http://localhost/?session=bridge-test' };
  globalThis.history = { replaceState() {} };
  globalThis.document = { hidden: false, addEventListener(name, fn) { listeners[name] = fn; } };
  globalThis.window = { addEventListener() {} };
  const b = new CellBridge({ session() {}, render() {}, log(s) { logs.push(s); } });
  b.protocol.epoch = 'scene'; b.connected = true; b.object = 'Cell';
  b.unity = { SendMessage(_, method, raw) {
    calls.push([method, raw]);
    if (method === 'OnUiEvent') b.sendEvent(raw);
  } };
  b.client = { connected: true, publish(topic, body, options, callback) { sent.push({ topic, body, options, callback }); } };
  return { b, calls, sent, logs, listeners, time(value) { now = value; } };
}

test('public broker rejection is visible and revokes local start permission', async t => {
  const { b, calls, sent, logs } = fixture(t);
  b.act('start');
  await Promise.resolve();
  assert.ok(calls.some(([m]) => m === 'OnStartToken'));
  sent[0].callback(new Error('Publish error: Quota exceeded'));
  assert.equal(b.pendingUi, null);
  assert.ok(logs[0].includes('Quota exceeded'));
  assert.deepEqual(calls.at(-1), ['OnControllerChanged', 'publish-rejected']);
  assert.equal(sent.length, 1, 'A rejected start is never automatically retried');
});

test('pending ordinary operations cannot duplicate feed; emergency bypasses pending state', t => {
  const { b, sent } = fixture(t);
  b.act('feed', false, 'blue_forward'); b.act('feed', false, 'blue_forward');
  assert.equal(sent.length, 1);
  b.act('estop');
  assert.equal(JSON.parse(sent.at(-1).body).data.action, 'estop');
});

test('diagnostic acknowledgements are limited; frozen browser locally holds before resume', t => {
  const { b, sent, calls, listeners, time } = fixture(t);
  for (let n = 0; n < 100; n++) { time(n * 50); b.ack('{"command_id":"test"}'); }
  assert.equal(sent.length, 3);
  listeners.freeze(); listeners.resume();
  assert.deepEqual(calls, [['OnVisibility', 'hidden'], ['OnVisibility', 'visible']]);
});

test('unacknowledged start times out locally without retrying it', async t => {
  const { b, calls, sent, logs, time } = fixture(t);
  b.act('start'); await Promise.resolve(); time(3100);
  assert.equal(b.uiBusy(), false);
  assert.deepEqual(calls.at(-1), ['OnControllerChanged', 'ui-timeout']);
  assert.ok(logs[0].includes('未确认'));
  assert.equal(sent.length, 1);
});
