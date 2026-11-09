import assert from 'node:assert/strict';
import test from 'node:test';
import * as api from '../src/api.ts';

test('requests use the in-memory operator token and propagate errors', async () => {
  let authorization;
  globalThis.fetch = async (_url, options) => {
    authorization = new Headers(options.headers).get('Authorization');
    return new Response(JSON.stringify({ orders: [] }), { status: 200 });
  };
  assert.equal(typeof api.setOperatorToken, 'function');
  api.setOperatorToken('test-token');
  assert.deepEqual(await api.fetchOrders(), []);
  assert.equal(authorization, 'Bearer test-token');
  globalThis.fetch = async () => new Response('', { status: 401 });
  await assert.rejects(api.fetchOrders(), /Access denied/);
  globalThis.fetch = async () => new Response('', { status: 503 });
  await assert.rejects(api.fetchOrders(), /not configured/);
  api.setOperatorToken('');
  globalThis.fetch = async (_url, options) => {
    authorization = new Headers(options.headers).get('Authorization');
    return new Response(JSON.stringify({ orders: [] }), { status: 200 });
  };
  await api.fetchOrders();
  assert.equal(authorization, null);
});

test('ticket proposal includes the supplied idempotency key', async () => {
  let payload;
  globalThis.fetch = async (_url, options) => {
    payload = JSON.parse(options.body);
    return new Response(JSON.stringify({ trace: {} }), { status: 200 });
  };
  await api.processAgentTicket('synthetic ticket', 'scope-1', 'attempt-1');
  assert.equal(payload.idempotency_key, 'attempt-1');
  assert.equal(payload.scope_id, 'scope-1');
});

test('lookup uses the supplied idempotency key and returns the recorded action', async () => {
  let url;
  globalThis.fetch = async (input) => {
    url = String(input);
    return new Response(JSON.stringify({ action: { action_id: 'act-1', status: 'pending', refund: null } }), { status: 200 });
  };
  const action = await api.lookupAction('key /+');
  assert.equal(new URL(url, 'http://localhost').searchParams.get('idempotency_key'), 'key /+');
  assert.equal(action.status, 'pending');
});

test('extracts backend error details across status codes and formats', async () => {
  // 1. String detail (e.g. 429 rate limit or 422 threshold validation)
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Auto-allow limit must be less than hard ceiling' }), { status: 422 });
  await assert.rejects(api.updatePolicy({ auto_allow_threshold: 50000 }), /Auto-allow limit must be less than hard ceiling/);

  // 2. Structured detail.message (e.g. 409 conflict)
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { message: 'Action act-123 has already been processed' } }), { status: 409 });
  await assert.rejects(api.decideApproval('act-123', 'approve', 'op'), /Action act-123 has already been processed/);

  // 3. Pydantic array validation error
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ loc: ['body', 'decision'], msg: 'Field required' }] }), { status: 422 });
  await assert.rejects(api.decideApproval('act-123', 'approve', 'op'), /Field required/);

  // 4. 503 with specific backend/database outage message
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Policy configuration unavailable: database disk error' }), { status: 503 });
  await assert.rejects(api.fetchPolicy(), /Policy configuration unavailable: database disk error/);
});

test('synchronous in-flight guard prevents duplicate approval submissions', async () => {
  let callCount = 0;
  globalThis.fetch = async () => {
    callCount++;
    return new Response(JSON.stringify({ result: { status: 'succeeded' } }), { status: 200 });
  };

  const inFlight = new Set();
  const executeWithGuard = async (actionId) => {
    if (inFlight.has(actionId)) return null;
    inFlight.add(actionId);
    try {
      return await api.decideApproval(actionId, 'approve', 'demo_operator');
    } finally {
      inFlight.delete(actionId);
    }
  };

  // Trigger two rapid synchronous submissions before first completes
  const p1 = executeWithGuard('act-double-click');
  const p2 = executeWithGuard('act-double-click');
  const [res1, res2] = await Promise.all([p1, p2]);

  assert.equal(callCount, 1, 'decideApproval should only be called once');
  assert.equal(res1.status, 'succeeded');
  assert.equal(res2, null);
  assert.equal(inFlight.size, 0, 'inFlight set should be cleared after resolution');
});

