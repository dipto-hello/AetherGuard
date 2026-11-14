import assert from 'node:assert/strict';
import test from 'node:test';
import { formatPolicyLimit, limitInputToUsdCents, policyLimitMinor } from '../src/policyMoney.ts';

test('a typed BDT limit is never enforced above the typed amount', () => {
  for (const typed of ['1000.00', '5000.00', '100.00', '6221.00', '0.99', '123456.78']) {
    const cents = limitInputToUsdCents(typed, 'BDT', 124.42);
    const enforced = policyLimitMinor(cents, 'BDT', 124.42);
    const [whole, fraction = ''] = typed.split('.');
    const typedMinor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
    assert.ok(enforced === null || enforced <= typedMinor, `${typed} enforced as ${enforced}`);
  }
  assert.equal(limitInputToUsdCents('6221.00', 'BDT', 124.42), 5000);
  assert.equal(limitInputToUsdCents('50.5', 'USD'), 5050);
  assert.equal(limitInputToUsdCents('1.234', 'USD'), null);
  assert.equal(limitInputToUsdCents('10', 'BDT'), null);
});

test('formats canonical USD cents and floors the equivalent BDT limit to whole poisha', () => {
  assert.equal(formatPolicyLimit(5500, 'USD'), '$55.00');
  assert.equal(formatPolicyLimit(5500, 'BDT', 124.42), '৳6,843.10');
  assert.equal(formatPolicyLimit(100000, 'BDT', 124.42), '৳124,420.00');
  assert.equal(formatPolicyLimit(1, 'BDT', 124.999999), '৳1.24');
  assert.equal(formatPolicyLimit(5500, 'BDT'), null);
});
