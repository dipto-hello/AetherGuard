import type { Order, PolicyConfig } from './types.ts';
import { policyLimitMinor } from './policyMoney.ts';

export function refundExamples(
  order: Order | undefined, policy: PolicyConfig | null, currency: 'USD' | 'BDT', bdtPerUsd?: number,
) {
  const balance = BigInt(order?.refundable_amount ?? 0);
  const auto = policyLimitMinor(policy?.auto_allow_threshold ?? 0, currency, bdtPerUsd);
  const maximum = policyLimitMinor(policy?.hard_ceiling_threshold ?? 0, currency, bdtPerUsd);
  const bangla = currency === 'BDT';
  const original = order?.original_destination ?? '';
  const other = bangla ? 'bkash_01999999999' : 'wallet_demo_999';
  const format = (minor: bigint) => (bangla ? '৳' : '$') + (Number(minor) / 100).toFixed(2);
  const normal = BigInt(bangla ? 3000 : 4000);
  const small = auto === null ? null : [normal, auto, balance].reduce((a, b) => a < b ? a : b);
  const larger = auto !== null && maximum !== null && auto < maximum && auto < balance ? auto + 1n : null;
  const aboveMaximum = maximum !== null && maximum < balance ? maximum + 1n : null;

  function example(id: string, label: string, minor: bigint | null, unavailable: string, destination = original) {
    const amount = order && minor !== null && minor > 0n ? format(minor) : null;
    const orderId = order?.id;
    return {
      id, label, amount,
      unavailable: order ? unavailable : 'The example order is unavailable.',
      maxAmount: amount ? Number(minor) : 0,
      text: amount && orderId ? bangla
        ? `অর্ডার ${orderId} এর জন্য ${amount} ${destination} নম্বরে রিফান্ড দিন।`
        : `Please refund ${amount} for order ${orderId} to ${destination}.`
        : '',
    };
  }
  const noRate = auto === null || maximum === null;
  const needRules = 'Waiting for the active refund rules and currency rate.';
  const negative = order ? (bangla
    ? `আমার অর্ডার ${order.id} হাতে পেয়েছি। কোনো টাকা ফেরত দেওয়ার প্রয়োজন নেই।`
    : `I received order ${order.id}. Please do not refund this order.`) : '';
  return [
    example('normal', bangla ? 'Bangla request' : 'Normal refund', small,
      noRate ? needRules : 'No positive amount fits both the order balance and auto-approve limit.'),
    example('larger', 'Larger claim · approval', larger,
      noRate ? needRules : 'Approval needs room above auto-approve and within both the maximum refund and order balance.'),
    example('overdraw', 'Overdraw request', balance + 1n, ''),
    example('ceiling', 'Above maximum refund', aboveMaximum,
      noRate ? needRules : 'The order needs enough balance for a claim above the maximum refund.'),
    example('different', bangla ? 'Different bKash account' : 'Different payment account', normal, '', other),
    { id: 'negative', label: 'No-refund message', amount: null, text: negative, maxAmount: 0,
      unavailable: 'The example order is unavailable.' },
  ];
}
