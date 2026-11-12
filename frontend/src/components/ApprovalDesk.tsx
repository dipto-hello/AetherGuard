import React, { useState, useRef } from 'react';
import type { PendingAction } from '../types';
import { decideApproval } from '../api';

interface ApprovalDeskProps {
  pendingActions: PendingAction[];
  currencyMode: 'USD' | 'BDT';
  onActionDecided: () => void | Promise<void>;
  onNavigateTab?: (tab: string) => void;
}

export const ApprovalDesk: React.FC<ApprovalDeskProps> = ({
  pendingActions,
  currencyMode,
  onActionDecided,
  onNavigateTab
}) => {
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<'executed' | 'rejected' | null>(null);
  const inFlightRef = useRef<Set<string>>(new Set());

  const handleDecision = async (actionId: string, decision: 'approve' | 'reject') => {
    if (inFlightRef.current.size > 0) return;
    inFlightRef.current.add(actionId);
    setProcessingId(actionId);
    setErrorMsg(null);
    setOutcome(null);

    try {
      const res = await decideApproval(actionId, decision, 'demo_operator');
      setOutcome(res.status === 'executed' ? 'executed' : 'rejected');
      await onActionDecided();
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      if (/expired|scope is missing/i.test(detail)) {
        setErrorMsg('Refund permission has expired. Run the ticket again to create a new request.');
      } else if (/already been processed|not found/i.test(detail)) {
        setErrorMsg('This request is no longer waiting for approval. Check Order balances for the result.');
        await onActionDecided();
      } else if (/fingerprint|current policy|scope maximum/i.test(detail)) {
        setErrorMsg('The request no longer meets the refund rules. Check the order balance and permissions before creating a new request.');
      } else {
        setErrorMsg('We could not confirm the decision. Check Order balances before trying again.');
        await onActionDecided();
      }
    } finally {
      inFlightRef.current.delete(actionId);
      setProcessingId(null);
    }
  };


  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-semibold tracking-tight text-white">Approvals</h1>
      <p className="mt-2 text-sm text-slate-300">Check the order, amount and payment destination before making a decision.</p>
      {errorMsg && <p role="alert" className="mt-4 rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-200">{errorMsg}</p>}
      {outcome && (
        <p role="status" className={`mt-4 rounded-lg border p-3 text-sm ${outcome === 'executed'
          ? 'border-emerald-800 bg-emerald-950/40 text-emerald-200'
          : 'border-red-800 bg-red-950/40 text-red-200'}`}>
          {outcome === 'executed' ? 'Refund approved and recorded.' : 'Refund rejected. The balance did not change.'}
        </p>
      )}
      <div className="mt-6 space-y-3">
        {pendingActions.length === 0 && (
          <div className="rounded-xl border border-borderSubtle bg-surface p-5">
            <p className="font-semibold text-white">No {currencyMode} refunds waiting for approval</p>
            {onNavigateTab && <button className="mt-2 text-sm text-emerald-300 underline" onClick={() => onNavigateTab('arena')}>Test a refund</button>}
          </div>
        )}
        {pendingActions.map((action) => {
          const currency = action.arguments?.currency ?? 'USD';
          const symbol = currency === 'BDT' ? '৳' : currency === 'USD' ? '$' : currency + ' ';
          const amount = symbol + ((action.arguments?.amount ?? 0) / 100).toFixed(2);
          const order = action.arguments?.order_id || 'Unknown';
          return (
            <article key={action.action_id} className="rounded-xl border border-amber-600/50 bg-surface p-5">
              <p className="mb-1 text-xs font-semibold text-amber-200">Waiting for approval</p>
              <h2 className="text-lg font-semibold text-white">{amount} refund for {order}</h2>
              <p className="mt-1 break-words text-sm text-slate-300">Payment destination: {action.arguments?.destination || 'Unknown'}</p>
              {action.created_at && <p className="mt-1 text-sm text-slate-400">Submitted {action.created_at} UTC</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                <button onClick={() => handleDecision(action.action_id, 'approve')} disabled={processingId !== null}
                  className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:opacity-50">
                  Approve sandbox refund
                </button>
                <button onClick={() => handleDecision(action.action_id, 'reject')} disabled={processingId !== null}
                  className="rounded-lg border border-borderStrong px-4 py-2 text-sm text-slate-200 hover:bg-background disabled:opacity-50">
                  Reject refund
                </button>
              </div>
              {processingId === action.action_id && <p role="status" className="mt-2 text-sm text-slate-300">Saving decision…</p>}
              <details className="mt-4 border-t border-borderSubtle pt-3 text-sm">
                <summary className="cursor-pointer text-slate-300">Request details</summary>
                <dl className="mt-2 space-y-1 break-all text-slate-400">
                  <div><dt className="inline">Request </dt><dd className="inline">{action.action_id}</dd></div>
                  <div><dt className="inline">Permission </dt><dd className="inline">{action.task_scope_id || 'Unknown'}</dd></div>
                  <div><dt className="inline">Fingerprint </dt><dd className="inline">{action.fingerprint}</dd></div>
                </dl>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
};
