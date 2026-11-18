import type { Order, PolicyConfig } from './types.ts';

const taka = (minor: bigint) => '৳' + (Number(minor) / 100).toFixed(2);
const positive = (value: number | undefined) =>
  value !== undefined && Number.isSafeInteger(value) && value > 0 ? BigInt(value) : null;
const smallest = (...values: bigint[]) => values.reduce((a, b) => a < b ? a : b);

type Text = (amount: string, orderId: string, destination: string) => string;
const english: Text = (amount, orderId, destination) => `Please refund ${amount} for order ${orderId} to ${destination}.`;
const bangla: Text = (amount, orderId, destination) => `অর্ডার ${orderId} এর জন্য ${amount} ${destination} নম্বরে রিফান্ড দিন।`;

export function refundExamples(orders: Order[], policy: PolicyConfig | null) {
  const find = (id: string) => orders.find((order) => order.id === id && order.currency === 'BDT');
  const main = find('ORD-101');
  const bkash = find('ORD-103');
  const balance = (order?: Order) => BigInt(order?.refundable_amount ?? 0);
  const auto = positive(policy?.auto_allow_threshold);
  const maximum = positive(policy?.hard_ceiling_threshold);
  const small = (order: Order | undefined, typical: bigint) =>
    auto === null || !order ? null : smallest(typical, auto, balance(order));
  const larger = auto !== null && maximum !== null && auto < maximum && auto < balance(main) ? auto + 1n : null;
  const aboveMaximum = maximum !== null && maximum < balance(main) ? maximum + 1n : null;
  const noRules = auto === null || maximum === null;
  const needRules = 'Waiting for the active refund rules.';

  function example(id: string, label: string, order: Order | undefined, minor: bigint | null, unavailable: string,
    text: Text = english, destination = order?.original_destination ?? '') {
    const amount = order && minor !== null && minor > 0n ? taka(minor) : null;
    return {
      id, label, order, amount,
      unavailable: order ? unavailable : 'The example order is unavailable.',
      maxAmount: amount ? Number(minor) : 0,
      text: amount && order ? text(amount, order.id, destination) : '',
    };
  }
  return [
    example('normal', 'Normal refund', main, small(main, 400_000n),
      noRules ? needRules : 'No positive amount fits both the order balance and auto-approve limit.'),
    example('bangla', 'Bangla request', bkash, small(bkash, 300_000n),
      noRules ? needRules : 'No positive amount fits both the order balance and auto-approve limit.', bangla),
    example('larger', 'Larger claim · approval', main, larger,
      noRules ? needRules : 'Approval needs room above auto-approve and within both the maximum refund and order balance.'),
    example('overdraw', 'Overdraw request', main, main ? balance(main) + 1n : null, ''),
    example('ceiling', 'Above maximum refund', main, aboveMaximum,
      noRules ? needRules : 'The order needs enough balance for a claim above the maximum refund.'),
    example('different', 'Different payment account', main, 400_000n, '', english, 'wallet_demo_999'),
    { id: 'negative', label: 'No-refund message', order: main, amount: null, maxAmount: 0,
      text: main ? `I received order ${main.id}. Please do not refund this order.` : '',
      unavailable: 'The example order is unavailable.' },
  ];
}
