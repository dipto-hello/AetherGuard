function rateMicros(bdtPerUsd?: number) {
  if (!bdtPerUsd || !Number.isFinite(bdtPerUsd) || bdtPerUsd < 0.000001 || bdtPerUsd > 1_000_000) return null;
  return BigInt(Math.round(bdtPerUsd * 1_000_000));
}

export function policyLimitMinor(cents: number, currency: 'USD' | 'BDT', bdtPerUsd?: number) {
  if (!Number.isSafeInteger(cents) || cents <= 0) return null;
  let minor = BigInt(cents);
  if (currency === 'BDT') {
    const micros = rateMicros(bdtPerUsd);
    if (micros === null) return null;
    minor = minor * micros / 1_000_000n;
  }
  return minor;
}

// Converts a typed limit to USD cents, rounding down so the enforced limit never exceeds what was typed.
export function limitInputToUsdCents(value: string, currency: 'USD' | 'BDT', bdtPerUsd?: number) {
  if (!/^\d{1,15}(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (currency === 'USD') return Number(minor);
  const micros = rateMicros(bdtPerUsd);
  return micros === null ? null : Number(minor * 1_000_000n / micros);
}

export function formatPolicyLimit(cents: number, currency: 'USD' | 'BDT', bdtPerUsd?: number) {
  const minor = policyLimitMinor(cents, currency, bdtPerUsd);
  if (minor === null) return null;
  return formatMinor(minor, currency);
}

export function formatMinor(minor: bigint, currency: 'USD' | 'BDT') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency, currencyDisplay: 'narrowSymbol',
  }).formatToParts(minor / 100n).map(({ type, value }) =>
    type === 'fraction' ? String(minor % 100n).padStart(2, '0') : value,
  ).join('');
}
