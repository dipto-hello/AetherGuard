import React, { useState } from 'react';
import { updateOrderPaidAmount } from '../api';
import type { Order, Refund } from '../types';
import { Database, RefreshCw, CreditCard, CheckCircle } from 'lucide-react';
import { decimalAmount, maxOrderMinor, parseTakaInput } from '../orderMoney';
import { formatMinor } from '../policyMoney';

interface SandboxViewerProps {
  orders: Order[];
  refunds: Refund[];
  onRefresh: () => Promise<boolean>;
  onOrderUpdated: (order: Order) => void;
}

function PaidAmountEditor({ order, onSaved }: { order: Order; onSaved: (order: Order) => void }) {
  const [draft, setDraft] = useState<{ order: Order; input?: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  if (!draft) return (
    <div>
      <button type="button" className="text-xs text-brand-300 underline" onClick={() => {
        setMessage('');
        setDraft({ order });
      }}>Edit paid total <span className="sr-only">for {order.id}</span></button>
      {message && <p className="mt-2 text-xs text-emerald-300" role="status">{message}</p>}
    </div>
  );
  const stored = BigInt(draft.order.paid_amount);
  const paid = draft.input === undefined ? stored : parseTakaInput(draft.input);
  const value = draft.input ?? decimalAmount(stored);
  const refunded = BigInt(draft.order.paid_amount - draft.order.refundable_amount);
  const valid = paid !== null && paid > 0n && paid <= maxOrderMinor && paid >= refunded;
  return (
    <form className="space-y-2" onSubmit={async (event) => {
      event.preventDefault();
      if (saving || !valid) return;
      setSaving(true);
      setMessage('');
      try {
        onSaved(await updateOrderPaidAmount(draft.order, Number(paid)));
        setDraft(null);
        setMessage('Paid total updated.');
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Could not update the order.');
      } finally {
        setSaving(false);
      }
    }}>
      <label className="block text-xs text-slate-200">
        Paid total (BDT)
        <input type="text" inputMode="decimal" maxLength={23} value={value} disabled={saving}
          onChange={(event) => { setDraft({ ...draft, input: event.target.value }); setMessage(''); }}
          className="mt-1 w-full rounded-lg border border-borderStrong bg-surface p-2 text-sm" />
      </label>
      <p className="text-xs text-slate-400">Already refunded: {formatMinor(refunded)}.</p>
      {valid && <p className="text-xs text-slate-300">Left to refund after saving: {formatMinor(paid - refunded)}.</p>}
      {!valid && <p className="text-xs text-rose-300">Enter a positive amount with up to two decimals. The saved total must cover existing refunds and fit the order’s supported range.</p>}
      {message && <p role="alert" className="text-xs text-rose-300">{message}</p>}
      <div className="flex gap-2 text-xs">
        <button type="submit" disabled={saving || !valid} className="rounded bg-brand-400 px-2.5 py-1.5 font-bold text-slate-950 disabled:opacity-50">{saving ? 'Saving…' : 'Save total'}</button>
        <button type="button" disabled={saving} className="px-2.5 py-1.5 text-slate-300" onClick={() => { setDraft(null); setMessage(''); }}>Cancel</button>
      </div>
    </form>
  );
}

export const SandboxViewer: React.FC<SandboxViewerProps> = ({ orders, refunds, onRefresh, onOrderUpdated }) => {
  // Legacy non-BDT records from before the taka-only change are shown in their own currency, read-only.
  const formatCurrency = (currency: string, minor: number) =>
    Number.isSafeInteger(minor) ? formatMinor(BigInt(minor), currency) : '—';
  const [refresh, setRefresh] = useState<{ state: 'loading' | 'done' | 'failed'; at?: string } | null>(null);
  const handleRefresh = async () => {
    setRefresh({ state: 'loading' });
    const ok = await onRefresh();
    setRefresh(ok ? { state: 'done', at: new Date().toLocaleTimeString() } : { state: 'failed' });
  };

  return (
    <div className="space-y-6">
      {/* Orders Grid Section */}
      <div className="bg-surface rounded-xl border border-borderSubtle p-6">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Database className="w-5 h-5 text-brand-400" />
              <h1 className="text-base font-bold text-white">
                Order balances
              </h1>
            </div>
            <p className="text-sm text-slate-400">
              All amounts are in Bangladeshi taka (BDT).
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <button
              onClick={handleRefresh}
              disabled={refresh?.state === 'loading'}
              className="px-3 py-1.5 rounded-lg bg-surfaceCard hover:bg-slate-800 border border-borderStrong text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-60 cursor-pointer"
              title="Reload order balances and refunds"
            >
              <RefreshCw aria-hidden="true" className={`w-3.5 h-3.5 text-brandCyan ${refresh?.state === 'loading' ? 'animate-spin' : ''}`} />
              <span>{refresh?.state === 'loading' ? 'Refreshing…' : 'Refresh'}</span>
            </button>
            <p role="status" className={`text-xs ${refresh?.state === 'failed' ? 'text-red-400' : 'text-slate-400'}`}>
              {refresh?.state === 'done' ? 'Updated ' + refresh.at : refresh?.state === 'failed' ? 'Could not refresh. Try again.' : ''}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          {orders.length === 0 && <p className="text-sm text-slate-400">No orders to show.</p>}
          {orders.map((ord) => {
            const percentage = ord.paid_amount > 0 ? Math.round(ord.refundable_amount / ord.paid_amount * 100) : 0;

            return (
              <div
                key={ord.id}
                className="p-4 rounded-xl bg-background border border-borderSubtle space-y-3 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-white">{ord.id} <span className="text-xs text-slate-400">{ord.currency === 'BDT' ? null : `Legacy ${ord.currency} · not refundable`}</span></span>
                  <span
                    className={`text-[10px] uppercase px-2 py-0.5 rounded-full font-bold font-mono ${
                      ord.status === 'paid'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : ord.status === 'partially_refunded'
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'
                    }`}
                  >
                    {ord.status.replace('_', ' ')}
                  </span>
                </div>

                <div>
                  <h4 className="text-xs font-semibold text-slate-200">{ord.customer_name}</h4>
                  <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400 mt-0.5">
                    <CreditCard className="w-3.5 h-3.5 text-slate-400" />
                    <span className="truncate">{ord.original_destination}</span>
                  </div>
                </div>

                {/* Balance Progress */}
                <div className="space-y-1.5 pt-2 border-t border-borderSubtle">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-slate-400">Left to refund</span>
                    <span className="text-emerald-400 font-bold text-sm">
                      {formatCurrency(ord.currency, ord.refundable_amount)}
                    </span>
                  </div>

                  <progress
                    aria-label={`Refundable balance for ${ord.id}`}
                    className="block w-full h-2 accent-brand-500"
                    value={ord.refundable_amount}
                    max={ord.paid_amount || 1}
                  />

                  <div className="flex justify-between text-[11px] font-mono text-slate-400">
                    <span>Paid {formatCurrency(ord.currency, ord.paid_amount)}</span>
                    <span>{percentage}% left</span>
                  </div>
                </div>
                {ord.currency === 'BDT' && <PaidAmountEditor order={ord} onSaved={onOrderUpdated} />}
              </div>
            );
          })}
        </div>
      </div>

      {/* Refunds History Table */}
      <div className="bg-surface rounded-xl border border-borderSubtle p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white">
              Completed Refunds ({refunds.length})
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            BDT refund history
          </span>
        </div>

        {refunds.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-xs font-mono border border-dashed border-borderStrong rounded-xl bg-background/40">
            No completed refunds yet.
          </div>
        ) : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Refund history">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-borderSubtle text-[11px] text-slate-400">
                  <th className="py-2.5 px-3 font-semibold">ID</th>
                  <th className="py-2.5 px-3 font-semibold">Order ID</th>
                  <th className="py-2.5 px-3 font-semibold">Refund Amount</th>
                  <th className="py-2.5 px-3 font-semibold">Sent To</th>
                  <th className="py-2.5 px-3 font-semibold">Request Key</th>
                  <th className="py-2.5 px-3 font-semibold">Executed At</th>
                  <th className="py-2.5 px-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-borderSubtle">
                {refunds.map((ref) => (
                  <tr key={ref.id} className="hover:bg-surfaceCard/60 transition">
                    <td className="py-2.5 px-3 text-white font-bold whitespace-nowrap">
                      {ref.id}
                    </td>
                    <td className="py-2.5 px-3 text-brand-400 font-semibold whitespace-nowrap">
                      {ref.order_id}
                    </td>
                    <td className="py-2.5 px-3 text-white font-bold whitespace-nowrap">
                      {formatCurrency(ref.currency, ref.amount)}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 break-all">
                      {ref.destination}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px] truncate max-w-[120px]">
                      {ref.idempotency_key}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {ref.created_at}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                        {ref.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
