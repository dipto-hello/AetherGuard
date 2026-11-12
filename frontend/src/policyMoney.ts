export function policyLimitMinor(cents: number, currency: 'USD' | 'BDT', bdtPerUsd?: number) {
  if (!Number.isSafeInteger(cents) || cents <= 0) return null;
  let minor = BigInt(cents);
  if (currency === 'BDT') {
    if (!bdtPerUsd || !Number.isFinite(bdtPerUsd) || bdtPerUsd < 0.000001 || bdtPerUsd > 1_000_000) return null;
    minor = minor * BigInt(Math.round(bdtPerUsd * 1_000_000)) / 1_000_000n;
  }
  return minor;
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
