import test from 'node:test';
import assert from 'node:assert/strict';
import { Protocol } from '../src/protocol.js';
function packet(extra={}) { return {v:1,session:'test-session',sender:'controller',peer:'python',epoch:'scene',seq:1,id:'one',sent_ms:10000,ttl_ms:3000,data:{},...extra}; }
function protocol() { const p = new Protocol('test-session'); p.epoch='scene'; return p; }
test('reject retained, old epoch, expired, future, malformed, duplicate and out of order',() => {
  const p=protocol();
  for(const m of [packet({epoch:'old'}),packet({sent_ms:0}),packet({sent_ms:30000}),packet({seq:NaN}),packet({data:[]})])
    assert.equal(p.accept(JSON.stringify(m),false,10000),null);
  assert.equal(p.accept(JSON.stringify(packet()),true,10000),null);
  assert.equal(p.accept('not json',false,10000),null);
  assert.ok(p.accept(JSON.stringify(packet({seq:2})),false,10000));
  assert.equal(p.accept(JSON.stringify(packet()),false,10000),null);
  assert.equal(p.accept(JSON.stringify(packet({seq:2})),false,10000),null);
});
test('single controller lease; retired controller cannot take over again',() => {
  const p=protocol();
  assert.ok(p.accept(JSON.stringify(packet()),false,10000));
  assert.equal(p.accept(JSON.stringify(packet({peer:'second'})),false,10001),null);
  assert.ok(p.accept(JSON.stringify(packet({peer:'second',sent_ms:14000})),false,14000));
  assert.equal(p.accept(JSON.stringify(packet({seq:3,sent_ms:18000})),false,18000),null);
});
