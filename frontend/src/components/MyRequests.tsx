import React, { useEffect } from 'react';
import { lookupAction } from '../api';
import { formatMinor } from '../policyMoney';
import { isOpen, statusLabel, type MyRequest } from '../myRequests';

const statusColor = (status: string) =>
  isOpen(status) ? 'text-amber-300' : status === 'executed' ? 'text-emerald-300' : 'text-red-300';

export const MyRequests: React.FC<{ requests: MyRequest[]; setRequests: (update: (current: MyRequest[]) => MyRequest[]) => void }> = ({ requests, setRequests }) => {
  const openKeys = requests.filter((r) => isOpen(r.status)).map((r) => r.key).join(',');

  useEffect(() => {
    if (!openKeys) return;
    const refresh = async () => {
      const updates = await Promise.allSettled(openKeys.split(',').map(async (key) => [key, (await lookupAction(key)).status] as const));
      const statuses = new Map(updates.flatMap((u) => u.status === 'fulfilled' ? [u.value] : []));
      if (statuses.size) setRequests((current) => current.map((r) => statuses.has(r.key) ? { ...r, status: statuses.get(r.key)! } : r));
    };
    void refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [openKeys, setRequests]);

  return (
    <section className="mt-6 rounded-xl border border-borderSubtle bg-surface p-4 sm:p-6" aria-labelledby="my-requests-heading">
      <h2 id="my-requests-heading" className="mb-4 text-lg font-semibold text-white">My requests</h2>
      {requests.length === 0 ? (
        <p className="text-sm text-slate-300">Refunds you request will appear here.</p>
      ) : (
        <ul className="divide-y divide-borderSubtle text-sm">
          {requests.map((r) => (
            <li key={r.key} className="flex items-center justify-between gap-3 py-2">
              <span>{r.orderId} · {formatMinor(BigInt(r.amount), 'BDT')}</span>
              <span className={`font-semibold ${statusColor(r.status)}`}>{statusLabel(r.status)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
