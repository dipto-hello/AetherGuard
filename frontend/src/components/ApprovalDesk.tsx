import React, { useState, useRef } from 'react';
import type { PendingAction } from '../types';
import { decideApproval } from '../api';
import { Check, X, Shield, Lock, Clock, AlertTriangle, Fingerprint } from 'lucide-react';

interface ApprovalDeskProps {
  pendingActions: PendingAction[];
  onActionDecided: () => void | Promise<void>;
}

export const ApprovalDesk: React.FC<ApprovalDeskProps> = ({ pendingActions, onActionDecided }) => {
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const inFlightRef = useRef<Set<string>>(new Set());

  const handleDecision = async (actionId: string, decision: 'approve' | 'reject') => {
    if (inFlightRef.current.has(actionId)) return;
    inFlightRef.current.add(actionId);
    setProcessingId(actionId);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await decideApproval(actionId, decision, 'demo_operator');
      setSuccessMsg(`Action #${actionId} successfully processed: status ${res.status}.`);
      await onActionDecided();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process approval decision');
    } finally {
      inFlightRef.current.delete(actionId);
      setProcessingId(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-surface rounded border border-borderSubtle p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div>
            <h1 className="text-xs font-bold uppercase tracking-wider text-inkPrimary flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>Human-in-the-Loop Approval Queue</span>
            </h1>
            <p className="text-xs text-inkMuted">
              Review the pending action details before approving or rejecting a refund.
            </p>
          </div>
          <span className="text-[11px] text-inkMuted font-mono">Reviewer: demo_operator (server-assigned)</span>
        </div>

        {errorMsg && (
          <div role="alert" aria-live="assertive" className="p-3 mb-3 rounded bg-red-950/20 border border-red-800/40 text-xs text-red-300 flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div role="status" aria-live="polite" className="p-3 mb-3 rounded bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-300 font-mono">
            {successMsg}
          </div>
        )}

        {pendingActions.length === 0 ? (
          <div className="text-center py-10 border border-dashed border-borderStrong rounded text-inkMuted text-xs">
            <Clock className="w-6 h-6 mx-auto mb-2 opacity-50 text-amber-400" />
            <p className="text-slate-300 font-medium">No actions currently pending approval.</p>
            <p className="text-[11px] text-inkMuted mt-1">
              Dispatch a high dispute refund ($250) from the Agent Arena to trigger a quarantined action.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingActions.map((action) => {
              const amount = action.arguments.amount ? (action.arguments.amount / 100).toFixed(2) : '0.00';
              const currency = action.arguments.currency || 'USD';
              const isProcessing = processingId === action.action_id;

              return (
                <div
                  key={action.action_id}
                  className="p-3.5 rounded bg-background border border-borderSubtle flex flex-col md:flex-row md:items-center justify-between gap-3"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-amber-400">#{action.action_id}</span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-surfaceCard text-slate-300 border border-borderSubtle">
                        {action.tool}
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        PENDING OPERATOR SIGN-OFF
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono text-inkMuted">
                      <div>
                        <span className="text-[10px] text-slate-400 block">Target Order:</span>
                        <span className="text-white font-semibold">{action.arguments.order_id || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block">Refund Amount:</span>
                        <span className="text-white font-semibold">{currency} {amount}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block">Destination:</span>
                        <span className="text-white break-all block">{action.arguments.destination || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block">Reason:</span>
                        <span className="text-slate-300 break-words block">{action.arguments.reason || 'N/A'}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 pt-1">
                      <Fingerprint className="w-3.5 h-3.5 text-slate-400" />
                      <span className="break-all">SHA-256 Fingerprint: {action.fingerprint}</span>
                    </div>
                    <p className="text-[10px] text-inkMuted break-all">Scope: {action.task_scope_id || 'Not provided'} · Created: {action.created_at}</p>
                  </div>

                  {/* Controls */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleDecision(action.action_id, 'approve')}
                      disabled={isProcessing || processingId !== null}
                      className="px-3 py-1.5 text-xs font-semibold rounded bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 transition disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{isProcessing ? 'Processing…' : 'Approve & Execute'}</span>
                    </button>
                    <button
                      onClick={() => handleDecision(action.action_id, 'reject')}
                      disabled={isProcessing || processingId !== null}
                      className="px-3 py-1.5 text-xs font-semibold rounded bg-surfaceCard hover:bg-red-950/40 text-slate-300 hover:text-red-300 border border-borderStrong transition disabled:opacity-50 flex items-center gap-1.5"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Security Invariants Box */}
      <div className="p-3.5 rounded bg-surfaceCard border border-borderSubtle text-xs font-mono text-inkMuted space-y-1">
        <div className="flex items-center gap-1.5 text-white font-semibold mb-1">
          <Shield className="w-3.5 h-3.5 text-slate-400" />
          <span>Review details:</span>
        </div>
        <p>Review the destination, amount, currency and reason before approving. A fingerprint helps identify the stored parameters; it is not a digital signature.</p>
      </div>
    </div>
  );
};
