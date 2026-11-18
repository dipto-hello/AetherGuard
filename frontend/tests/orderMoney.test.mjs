import assert from 'node:assert/strict';
import test from 'node:test';
import { decimalAmount, parseTakaInput } from '../src/orderMoney.ts';

test('taka input parses to exact poisha', () => {
  assert.equal(parseTakaInput('100.01'), 10001n);
  assert.equal(parseTakaInput('5000'), 500000n);
  assert.equal(parseTakaInput('0.5'), 50n);
  assert.equal(parseTakaInput('100.001'), null);
  assert.equal(parseTakaInput('-1'), null);
  assert.equal(parseTakaInput(''), null);
  assert.equal(decimalAmount(500005n), '5000.05');
});
