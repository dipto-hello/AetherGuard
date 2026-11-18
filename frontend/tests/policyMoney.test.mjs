import assert from 'node:assert/strict';
import test from 'node:test';
import { formatMinor, formatPolicyLimit, limitInputToPoisha } from '../src/policyMoney.ts';

test('typed taka limits are stored as exact poisha', () => {
  assert.equal(limitInputToPoisha('5000'), 500000);
  assert.equal(limitInputToPoisha('6221.50'), 622150);
  assert.equal(limitInputToPoisha('1.234'), null);
  assert.equal(limitInputToPoisha('abc'), null);
});

test('formats poisha limits as taka without conversion', () => {
  assert.equal(formatPolicyLimit(500000), '৳5,000.00');
  assert.equal(formatPolicyLimit(10000000), '৳100,000.00');
  assert.equal(formatPolicyLimit(1), '৳0.01');
  assert.equal(formatPolicyLimit(0), null);
  assert.equal(formatMinor(4000n, 'USD'), '$40.00');
});
