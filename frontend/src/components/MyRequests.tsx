import React, { useEffect } from 'react';
import { CircleCheck, CircleX, Clock3, Inbox } from 'lucide-react';
import { lookupAction } from '../api';
import { formatMinor } from '../policyMoney';
import { isOpen, statusLabel, type MyRequest } from '../myRequests';

const statusStyle = (status: string) =>
  isOpen(status) ? ['bg-amber-50 text-amber-900 border-amber-200', Clock3] as const
  : status === 'executed' ? ['bg-emerald-50 text-emerald-800 border-emerald-200', CircleCheck] as const
  : ['bg-red-50 text-red-800 border-red-200', CircleX] as const;

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
    <section className="user-card mx-auto mt-6 max-w-5xl p-5 sm:p-6" aria-labelledby="my-requests-heading">
      <h2 id="my-requests-heading" className="mb-4 text-lg font-semibold text-slate-900">My requests</h2>
      {requests.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500"><Inbox className="mx-auto mb-2 h-7 w-7 text-slate-400" aria-hidden="true" />Refunds you request will appear here.</div>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {requests.map((r) => {
            const [style, Icon] = statusStyle(r.status);
            return (
              <li key={r.key} className="flex items-center justify-between gap-3 py-3">
                <span className="text-slate-700"><span className="font-semibold text-slate-900">{r.orderId}</span> · {formatMinor(BigInt(r.amount), 'BDT')}</span>
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-semibold ${style}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />{statusLabel(r.status)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};
