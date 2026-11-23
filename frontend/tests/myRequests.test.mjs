import assert from 'node:assert/strict';
import test from 'node:test';
import { statusLabel, loadMyRequests, saveMyRequests } from '../src/myRequests.ts';

test('user sees pending, accepted or rejected for each request', () => {
  assert.equal(statusLabel('pending'), 'Pending');
  assert.equal(statusLabel('executing'), 'Pending');
  assert.equal(statusLabel('executed'), 'Accepted');
  assert.equal(statusLabel('rejected'), 'Rejected');
  assert.equal(statusLabel('expired'), 'Closed');
});

test('requests survive a reload and storage failures do not throw', () => {
  const store = new Map();
  globalThis.localStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const saved = [{ key: 'k1', orderId: 'ORD-101', amount: 2500000, status: 'pending' }];
  saveMyRequests(saved);
  assert.deepEqual(loadMyRequests(), saved);
  globalThis.localStorage = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.deepEqual(loadMyRequests(), []);
  saveMyRequests(saved);
  delete globalThis.localStorage;
});
