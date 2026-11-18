import { parseTakaInput } from './orderMoney.ts';

// Refund rules are stored and enforced in poisha; there is no currency conversion.
export function limitInputToPoisha(value: string) {
  const minor = parseTakaInput(value, 15);
  return minor === null ? null : Number(minor);
}

export function formatPolicyLimit(poisha: number) {
  if (!Number.isSafeInteger(poisha) || poisha <= 0) return null;
  return formatMinor(BigInt(poisha));
}

// Formats integer minor units. Legacy non-BDT records from before the taka-only change keep their own code.
export function formatMinor(minor: bigint, currency = 'BDT') {
  let parts;
  try {
    parts = new Intl.NumberFormat('en-US', { style: 'currency', currency, currencyDisplay: 'narrowSymbol' })
      .formatToParts(minor / 100n);
  } catch {
    return `${currency} ${minor / 100n}.${String(minor % 100n).padStart(2, '0')}`;
  }
  return parts.map(({ type, value }) =>
    type === 'fraction' ? String(minor % 100n).padStart(2, '0') : value,
  ).join('');
}
