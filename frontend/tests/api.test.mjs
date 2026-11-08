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
