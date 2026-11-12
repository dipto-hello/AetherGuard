import assert from 'node:assert/strict';
import test from 'node:test';
import { refundExamples } from '../src/refundExamples.ts';

test('BDT example amounts follow policy and balance down to one poisha', () => {
  const order = { id: 'ORD-103', refundable_amount: 3500, original_destination: 'bkash_01711000000' };
  const policy = { auto_allow_threshold: 10, hard_ceiling_threshold: 20 };
  const amounts = (balance, rules = policy, rate = 124.50) =>
    Object.fromEntries(refundExamples({ ...order, refundable_amount: balance }, rules, 'BDT', rate)
      .map((example) => [example.id, example.maxAmount]));
  assert.deepEqual(amounts(3500), { normal: 1245, larger: 1246, overdraw: 3501, ceiling: 2491, different: 3000, negative: 0 });
  assert.deepEqual(amounts(1000), { normal: 1000, larger: 0, overdraw: 1001, ceiling: 0, different: 3000, negative: 0 });
  assert.equal(amounts(3500, { ...policy, hard_ceiling_threshold: 10 }).larger, 0);
  assert.equal(amounts(3500, policy, 125).larger, 1251);
  assert.equal(refundExamples(order, policy, 'BDT')[0].text, '');
});

test('USD examples use the order and exact USD cents', () => {
  const list = refundExamples({ id: 'ORD-101', refundable_amount: 5000, original_destination: 'card_visa_4242' },
    { auto_allow_threshold: 1000, hard_ceiling_threshold: 2000 }, 'USD');
  assert.match(list[0].text, /\$10\.00.*ORD-101.*card_visa_4242/);
  assert.equal(list.find((item) => item.id === 'larger').maxAmount, 1001);
  assert.equal(list.find((item) => item.id === 'overdraw').maxAmount, 5001);
  assert.match(list.find((item) => item.id === 'different').text, /wallet_demo_999/);
});
