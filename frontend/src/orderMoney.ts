export type Currency = 'USD' | 'BDT';

export const maxOrderMinor = 999_999_999_999n;

export function convertOrderMinor(minor: bigint, from: Currency, to: Currency, rate?: number) {
  if (from === to) return minor;
  if (!rate || !Number.isFinite(rate) || rate < 0.000001 || rate > 1_000_000) return null;
  const micros = BigInt(Math.round(rate * 1_000_000));
  const scale = 1_000_000n;
  const [numerator, denominator] = from === 'USD' ? [micros, scale] : [scale, micros];
  return (minor * numerator + denominator / 2n) / denominator;
}

export function decimalAmount(minor: bigint) {
  return `${minor / 100n}.${String(minor % 100n).padStart(2, '0')}`;
}

export function orderTotalFromInput(value: string, stored: bigint, from: Currency, to: Currency, rate?: number) {
  if (!/^\d{1,20}(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  const entered = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  // Saving an unchanged converted display must preserve the original minor units.
  if (entered === convertOrderMinor(stored, to, from, rate)) return stored;
  return convertOrderMinor(entered, from, to, rate);
}
