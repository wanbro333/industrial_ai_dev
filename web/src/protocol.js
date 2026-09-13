export const MAX_BYTES = 32768;
export function validSession(value) { return /^[a-zA-Z0-9_-]{8,64}$/.test(value ?? ''); }
export class Protocol {
  constructor(session) {
    if (!validSession(session)) throw new Error('Invalid session');
    this.session = session;
    this.peer = crypto.randomUUID().replaceAll('-', '');
    this.seq = 0;
    this.epoch = '';
    this.controller = '';
    this.highest = 0;
    this.lastReceived = -Infinity;
    this.retiredPeers = new Set();
  }
  make(data) {
    this.seq += 1;
    return { v: 1, session: this.session, sender: 'simulator', peer: this.peer,
      epoch: this.epoch, seq: this.seq, id: `${this.peer}:${this.seq}`,
      sent_ms: Date.now(), ttl_ms: 3000, data };
  }
  accept(raw, retained = false, now = Date.now()) {
    if (retained || raw.length > MAX_BYTES) return null;
    let msg;
    try { msg = JSON.parse(raw); } catch { return null; }
    if (!msg || msg.v !== 1 || msg.session !== this.session || msg.sender !== 'controller'
      || msg.epoch !== this.epoch || typeof msg.peer !== 'string' || !msg.peer || msg.peer.length > 128
      || typeof msg.id !== 'string' || !msg.id || msg.id.length > 128
      || !Number.isSafeInteger(msg.seq) || msg.seq < 1
      || !Number.isSafeInteger(msg.sent_ms) || !Number.isSafeInteger(msg.ttl_ms)
      || msg.ttl_ms < 1 || msg.ttl_ms > 5000 || now - msg.sent_ms > msg.ttl_ms || msg.sent_ms - now > 5000
      || typeof msg.data !== 'object' || msg.data === null || Array.isArray(msg.data)) return null;
    if (this.retiredPeers.has(msg.peer)) return null;
    if (this.controller && msg.peer !== this.controller) {
      if (now - this.lastReceived <= 3000) return null;
      this.retiredPeers.add(this.controller);
      this.highest = 0;
    }
    if (msg.seq <= this.highest) return null;
    this.controller = msg.peer;
    this.highest = msg.seq;
    this.lastReceived = now;
    return msg;
  }
}
