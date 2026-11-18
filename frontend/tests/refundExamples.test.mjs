import assert from 'node:assert/strict';
import test from 'node:test';
import { refundExamples } from '../src/refundExamples.ts';

const orders = (main = 2500000, bkash = 500000) => [
  { id: 'ORD-101', currency: 'BDT', refundable_amount: main, original_destination: 'card_visa_4242' },
  { id: 'ORD-103', currency: 'BDT', refundable_amount: bkash, original_destination: 'bkash_01711000000' },
];
const policy = { auto_allow_threshold: 500000, hard_ceiling_threshold: 10000000 };
const amounts = (list) => Object.fromEntries(list.map((example) => [example.id, example.maxAmount]));

test('taka examples follow policy and balance down to one poisha', () => {
  assert.deepEqual(amounts(refundExamples(orders(), policy)),
    { normal: 400000, bangla: 300000, larger: 500001, overdraw: 2500001, ceiling: 0, different: 400000, negative: 0 });
  assert.deepEqual(amounts(refundExamples(orders(20000000, 1000), policy)),
    { normal: 400000, bangla: 1000, larger: 500001, overdraw: 20000001, ceiling: 10000001, different: 400000, negative: 0 });
  assert.equal(amounts(refundExamples(orders(), { ...policy, hard_ceiling_threshold: 500000 })).larger, 0);
  assert.equal(refundExamples(orders(), null)[0].text, '');
});

test('examples use the order, taka amounts, and language', () => {
  const list = refundExamples(orders(), policy);
  assert.match(list[0].text, /৳4000\.00.*ORD-101.*card_visa_4242/);
  assert.match(list.find((item) => item.id === 'bangla').text, /অর্ডার ORD-103.*৳3000\.00.*bkash_01711000000/);
  assert.match(list.find((item) => item.id === 'different').text, /wallet_demo_999/);
  assert.equal(list.find((item) => item.id === 'bangla').order.id, 'ORD-103');
});

test('legacy non-BDT orders are not used for examples', () => {
  const list = refundExamples([{ ...orders()[0], currency: 'USD' }], policy);
  assert.equal(list[0].text, '');
  assert.equal(list[0].unavailable, 'The example order is unavailable.');
});
