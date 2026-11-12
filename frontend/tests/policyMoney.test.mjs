import assert from 'node:assert/strict';
import test from 'node:test';
import { formatPolicyLimit } from '../src/policyMoney.ts';

test('formats canonical USD cents and floors the equivalent BDT limit to whole poisha', () => {
  assert.equal(formatPolicyLimit(5500, 'USD'), '$55.00');
  assert.equal(formatPolicyLimit(5500, 'BDT', 124.42), '৳6,843.10');
  assert.equal(formatPolicyLimit(100000, 'BDT', 124.42), '৳124,420.00');
  assert.equal(formatPolicyLimit(1, 'BDT', 124.999999), '৳1.24');
  assert.equal(formatPolicyLimit(5500, 'BDT'), null);
});
