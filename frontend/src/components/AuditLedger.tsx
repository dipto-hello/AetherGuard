import React from 'react';
import type { AuditEvent } from '../types';
import { History, CheckCircle, AlertOctagon, Clock } from 'lucide-react';

interface AuditLedgerProps {
  logs: AuditEvent[];
}

export const AuditLedger: React.FC<AuditLedgerProps> = ({ logs }) => {
  return (
    <div className="bg-surface rounded border border-borderSubtle p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h1 className="text-xs font-bold uppercase tracking-wider text-inkPrimary flex items-center gap-1.5">
            <History className="w-3.5 h-3.5 text-inkMuted" />
            <span>Governance Audit History</span>
          </h1>
          <p className="text-xs text-inkMuted">
            Recorded governance decisions and fingerprints. This history is not tamper-proof.
          </p>
        </div>
        <span className="text-[10px] font-mono text-inkMuted bg-surfaceCard border border-borderSubtle px-2 py-0.5 rounded">
          {logs.length} Recorded Events
        </span>
      </div>

      {logs.length === 0 ? (
        <div className="text-center py-10 text-inkMuted text-xs font-mono border border-dashed border-borderStrong rounded">
          No audit records logged yet. Dispatch an action in the Agent Arena.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono border-collapse">
            <thead>
              <tr className="border-b border-borderSubtle text-[11px] text-inkMuted">
                <th className="py-2 px-2.5 font-normal">Timestamp</th>
                <th className="py-2 px-2.5 font-normal">Action ID</th>
                <th className="py-2 px-2.5 font-normal">Tool</th>
                <th className="py-2 px-2.5 font-normal">Verdict</th>
                <th className="py-2 px-2.5 font-normal">Decision Reason</th>
                <th className="py-2 px-2.5 font-normal">SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderSubtle">
              {logs.map((log) => {
                const isAllowed = log.verdict === 'ALLOWED' || log.verdict === 'APPROVED';
                const isBlocked = log.verdict === 'BLOCKED' || log.verdict === 'REJECTED';
                const isPending = log.verdict === 'APPROVAL_REQUIRED';

                return (
                  <tr key={log.id} className="hover:bg-surfaceCard/50 transition">
                    <td className="py-2 px-2.5 text-inkMuted whitespace-nowrap">
                      {log.created_at}
                    </td>
                    <td className="py-2 px-2.5 text-white font-medium whitespace-nowrap">
                      {log.action_id}
                    </td>
                    <td className="py-2 px-2.5 text-slate-300 whitespace-nowrap">
                      {log.tool}
                    </td>
                    <td className="py-2 px-2.5 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                          isAllowed
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : isPending
                            ? 'bg-amber-500/10 text-amber-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {isAllowed && <CheckCircle className="w-3 h-3" />}
                        {isPending && <Clock className="w-3 h-3" />}
                        {isBlocked && <AlertOctagon className="w-3 h-3" />}
                        <span>{log.verdict}</span>
                      </span>
                    </td>
                    <td className="py-2 px-2.5 text-slate-300 text-[11px]">
                      {log.reason}
                    </td>
                    <td className="py-2 px-2.5 text-slate-500 text-[10px] truncate max-w-[160px]">
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
