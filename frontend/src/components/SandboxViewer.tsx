import React from 'react';
import type { Order, Refund } from '../types';
import { Database, RefreshCw, CreditCard } from 'lucide-react';

interface SandboxViewerProps {
  orders: Order[];
  refunds: Refund[];
  onRefresh: () => void;
}

export const SandboxViewer: React.FC<SandboxViewerProps> = ({ orders, refunds, onRefresh }) => {
  return (
    <div className="space-y-5">
      {/* Orders Grid */}
      <div className="bg-surface rounded border border-borderSubtle p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xs font-bold uppercase tracking-wider text-inkPrimary flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-inkMuted" />
              <span>Authoritative Enterprise Sandbox DB</span>
            </h1>
            <p className="text-xs text-inkMuted">
              Current synthetic orders and recorded refund history.
            </p>
          </div>
          <button
            onClick={onRefresh}
            className="p-1.5 rounded bg-surfaceCard border border-borderSubtle text-slate-300 hover:text-white transition"
            title="Refresh database state"
            aria-label="Refresh database state"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {orders.map((ord) => {
            const paid = (ord.paid_amount / 100).toFixed(2);
            const refundable = (ord.refundable_amount / 100).toFixed(2);
            const percentage = Math.round((ord.refundable_amount / ord.paid_amount) * 100);

            return (
              <div key={ord.id} className="p-3.5 rounded bg-background border border-borderSubtle space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-white">{ord.id}</span>
                  <span
                    className={`text-[9px] uppercase px-1.5 py-0.2 rounded font-semibold font-mono ${
                      ord.status === 'paid'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : ord.status === 'partially_refunded'
                        ? 'bg-amber-500/10 text-amber-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}
                  >
                    {ord.status.replace('_', ' ')}
                  </span>
                </div>

                <div>
                  <h4 className="text-xs font-medium text-slate-200">{ord.customer_name}</h4>
                  <div className="flex items-center gap-1 text-[11px] font-mono text-inkMuted mt-0.5">
                    <CreditCard className="w-3 h-3 text-slate-500" />
                    <span>{ord.original_destination}</span>
                  </div>
                </div>

                {/* Balance Progress */}
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] font-mono">
                    <span className="text-inkMuted">Refundable:</span>
                    <span className="text-white font-semibold tabular-nums">
                      {ord.currency} {refundable}
                    </span>
                  </div>
                  <progress
                    className="w-full h-1 accent-emerald-500"
                    value={percentage}
                    max={100}
                    aria-label={`Refundable balance for ${ord.id}`}
                  />
                  <div className="flex justify-between text-[10px] font-mono text-slate-500">
                    <span>Paid: {ord.currency} {paid}</span>
                    <span className="tabular-nums">{percentage}% remaining</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Refunds History Table */}
      <div className="bg-surface rounded border border-borderSubtle p-4">
        <h3 className="text-xs font-semibold text-inkPrimary mb-3">
          Executed Refund Audit Trail ({refunds.length})
        </h3>

        {refunds.length === 0 ? (
          <div className="text-center py-8 text-inkMuted text-xs font-mono border border-dashed border-borderStrong rounded">
            No refunds executed yet. Allowed actions and approved requests appear here.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-borderSubtle text-[11px] text-inkMuted">
                  <th className="py-2 px-2.5 font-normal">Refund ID</th>
                  <th className="py-2 px-2.5 font-normal">Order</th>
                  <th className="py-2 px-2.5 font-normal">Amount</th>
                  <th className="py-2 px-2.5 font-normal">Destination</th>
                  <th className="py-2 px-2.5 font-normal">Idempotency Key</th>
                  <th className="py-2 px-2.5 font-normal">Executed At</th>
                  <th className="py-2 px-2.5 font-normal">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-borderSubtle">
                {refunds.map((ref) => (
                  <tr key={ref.id} className="hover:bg-surfaceCard/50 transition">
                    <td className="py-2 px-2.5 text-white font-medium whitespace-nowrap">
                      {ref.id}
                    </td>
                    <td className="py-2 px-2.5 text-slate-300 whitespace-nowrap">
                      {ref.order_id}
                    </td>
                    <td className="py-2 px-2.5 text-emerald-400 font-semibold tabular-nums whitespace-nowrap">
                      {ref.currency} {(ref.amount / 100).toFixed(2)}
                    </td>
                    <td className="py-2 px-2.5 text-inkMuted whitespace-nowrap">
                      {ref.destination}
                    </td>
                    <td className="py-2 px-2.5 text-slate-500 text-[10px] truncate max-w-[140px]">
                      {ref.idempotency_key}
                    </td>
                    <td className="py-2 px-2.5 text-inkMuted text-[10px] whitespace-nowrap">
                      {ref.created_at}
                    </td>
                    <td className="py-2 px-2.5 whitespace-nowrap">
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400">
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
