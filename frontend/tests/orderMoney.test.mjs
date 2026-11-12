import assert from 'node:assert/strict';
import test from 'node:test';
import { convertOrderMinor, orderTotalFromInput } from '../src/orderMoney.ts';

test('an unchanged converted input preserves the native balance', () => {
  const rate = 124.610683;
  assert.equal(convertOrderMinor(500000n, 'BDT', 'USD', rate), 4012n);
  assert.equal(orderTotalFromInput('40.12', 500000n, 'USD', 'BDT', rate), 500000n);
  assert.equal(orderTotalFromInput('50.00', 500000n, 'USD', 'BDT', rate), 623053n);
});

test('BDT edits round to native USD cents and require a quote', () => {
  assert.equal(orderTotalFromInput('124.99', 25000n, 'BDT', 'USD', 125), 100n);
  assert.equal(orderTotalFromInput('124.99', 25000n, 'BDT', 'USD'), null);
  assert.equal(orderTotalFromInput('100.001', 25000n, 'USD', 'USD'), null);
  assert.equal(orderTotalFromInput('100.01', 25000n, 'USD', 'USD'), 10001n);
});
