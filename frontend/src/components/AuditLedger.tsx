import React from 'react';
import type { AuditEvent } from '../types';
import { History, CheckCircle, AlertOctagon, Clock } from 'lucide-react';

interface AuditLedgerProps {
  logs: AuditEvent[];
}

export const AuditLedger: React.FC<AuditLedgerProps> = ({ logs }) => {
  return (
    <div className="bg-surface rounded-xl border border-borderSubtle p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <History className="w-5 h-5 text-brand-400" />
            <h1 className="text-base font-bold text-white">
              Activity
            </h1>
          </div>
          <p className="text-sm text-slate-400">
            Recent refund decisions and demo changes across both currencies.
          </p>
        </div>
        <span className="self-start sm:self-auto text-xs font-mono text-brand-400 bg-brand-950/40 border border-brand-800/60 px-3 py-1 rounded-full font-semibold">
          {logs.length} events shown
        </span>
      </div>

      {logs.length === 0 ? (
        <div className="text-center py-10 text-slate-400 text-xs font-mono border border-dashed border-borderStrong rounded-xl bg-background/40">
          No activity yet. Run an example in "Test a refund" to see records here.
        </div>
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Recent activity">
          <table className="w-full text-left text-xs font-mono border-collapse">
            <thead>
              <tr className="border-b border-borderSubtle text-[11px] text-slate-400">
                <th className="py-2.5 px-3 font-semibold">Date &amp; Time</th>
                <th className="py-2.5 px-3 font-semibold">ID</th>
                <th className="py-2.5 px-3 font-semibold">Action</th>
                <th className="py-2.5 px-3 font-semibold">Result</th>
                <th className="py-2.5 px-3 font-semibold">Reason</th>
                <th className="py-2.5 px-3 font-semibold">Action fingerprint</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderSubtle">
              {logs.map((log) => {
                const isAllowed = log.verdict === 'ALLOWED' || log.verdict === 'APPROVED';
                const isBlocked = log.verdict === 'BLOCKED' || log.verdict === 'REJECTED';
                const isPending = log.verdict === 'APPROVAL_REQUIRED';

                return (
                  <tr key={log.id} className="hover:bg-surfaceCard/60 transition">
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {log.created_at}
                    </td>
                    <td className="py-2.5 px-3 text-white font-bold whitespace-nowrap">
                      {log.action_id}
                    </td>
                    <td className="py-2.5 px-3 text-brand-400 whitespace-nowrap">
                      {log.tool}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold ${
                          isAllowed
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : isPending
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : isBlocked
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : 'bg-slate-800 text-slate-300 border border-slate-700'
                        }`}
                      >
                        {isAllowed && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                        {isPending && <Clock className="w-3 h-3 text-amber-400" />}
                        {isBlocked && <AlertOctagon className="w-3 h-3 text-red-400" />}
                        <span>{log.verdict}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 max-w-xs break-words">
                      {log.reason}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px] truncate max-w-[150px]">
                      {log.fingerprint || 'N/A'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
