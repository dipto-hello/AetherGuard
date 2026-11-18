// All amounts are Bangladeshi taka stored as integer poisha (৳1 = 100 poisha).
export const maxOrderMinor = 999_999_999_999n;

export function decimalAmount(minor: bigint) {
  return `${minor / 100n}.${String(minor % 100n).padStart(2, '0')}`;
}

export function parseTakaInput(value: string, maxDigits = 20) {
  if (!new RegExp(`^\\d{1,${maxDigits}}(?:\\.\\d{1,2})?$`).test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
}
