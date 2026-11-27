import React, { useState, useRef } from 'react';
import type { PendingAction } from '../types';
import { decideApproval } from '../api';
import { formatMinor } from '../policyMoney';
import { AnimatePresence, motion } from 'motion/react';

interface ApprovalDeskProps {
  pendingActions: PendingAction[];
  onActionDecided: () => void | Promise<void>;
  onNavigateTab?: (tab: string) => void;
}

export const ApprovalDesk: React.FC<ApprovalDeskProps> = ({
  pendingActions,
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
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-borderSubtle pb-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Approvals</h1>
          <p className="mt-1 text-sm text-slate-400">Check the order, amount and payment destination before making a decision.</p>
        </div>
        <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-sm font-semibold text-amber-300">{pendingActions.length} waiting</span>
      </div>
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
            <p className="font-semibold text-white">No refunds waiting for approval</p>
            {onNavigateTab && <button className="mt-2 text-sm text-brand-300 underline" onClick={() => onNavigateTab('arena')}>Test a refund</button>}
          </div>
        )}
        <AnimatePresence initial={false}>
        {pendingActions.map((action) => {
          const rawAmount = action.arguments?.amount;
          const amount = Number.isSafeInteger(rawAmount)
            ? formatMinor(BigInt(rawAmount as number), action.arguments?.currency ?? 'BDT') : 'Unknown amount';
          const order = action.arguments?.order_id || 'Unknown';
          return (
            <motion.article
              key={action.action_id}
              layout
              exit={{ opacity: 0, x: 24, transition: { duration: 0.2, ease: 'easeIn' } }}
              transition={{ type: 'spring', bounce: 0, visualDuration: 0.3 }}
              className="rounded-xl border border-borderSubtle border-l-4 border-l-amber-400 bg-surface p-5"
            >
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-amber-300">Waiting for approval</p>
              <h2 className="text-lg font-semibold text-white">{amount} refund for {order}</h2>
              <p className="mt-1 break-words text-sm text-slate-300">Payment destination: {action.arguments?.destination || 'Unknown'}</p>
              {action.arguments?.reason?.startsWith('AI judge unsure: ') && (
                <p className="mt-2 rounded border border-amber-600/40 bg-amber-950/30 p-2 text-sm text-amber-100">
                  <strong>AI judge was unsure:</strong> {action.arguments.reason.slice('AI judge unsure: '.length)}
                </p>
              )}
              {action.created_at && <p className="mt-1 text-sm text-slate-400">Submitted {action.created_at} UTC</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                <button onClick={() => handleDecision(action.action_id, 'approve')} disabled={processingId !== null}
                  className="min-h-[2.5rem] rounded-md bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:opacity-50 cursor-pointer">
                  Approve sandbox refund
                </button>
                <button onClick={() => handleDecision(action.action_id, 'reject')} disabled={processingId !== null}
                  className="min-h-[2.5rem] rounded-md border border-red-500/40 px-4 py-2 text-sm font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50 cursor-pointer">
                  Reject refund
                </button>
              </div>
              {processingId === action.action_id && <p role="status" className="mt-2 text-sm text-slate-300">Saving decision…</p>}
              <details className="mt-4 border-t border-borderSubtle pt-3 text-sm">
                <summary className="cursor-pointer text-slate-300">Request details</summary>
                <dl className="mt-2 space-y-1 break-all font-mono text-xs text-slate-400">
                  <div><dt className="inline">Request </dt><dd className="inline">{action.action_id}</dd></div>
                  <div><dt className="inline">Permission </dt><dd className="inline">{action.task_scope_id || 'Unknown'}</dd></div>
                  <div><dt className="inline">Fingerprint </dt><dd className="inline">{action.fingerprint}</dd></div>
                </dl>
              </details>
            </motion.article>
          );
        })}
        </AnimatePresence>
      </div>
    </section>
  );
};
