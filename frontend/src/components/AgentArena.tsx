import React, { useRef, useState } from 'react';
import { CircleCheck, CircleX, Clock3 } from 'lucide-react';
import type { AgentTrace, Order, PolicyConfig } from '../types';
import { refundExamples } from '../refundExamples';
import { processAgentTicket, createTaskScope, lookupAction } from '../api';

interface AgentArenaProps {
  onActionComplete: () => void;
  unknownAttempt: string | null;
  setUnknownAttempt: (key: string | null) => void;
  onNavigateTab?: (tab: string) => void;
  currencyMode: 'USD' | 'BDT';
  orders: Order[];
  policy: PolicyConfig | null;
  bdtPerUsd?: number;
}

export const AgentArena: React.FC<AgentArenaProps> = ({
  onActionComplete,
  unknownAttempt,
  setUnknownAttempt,
  onNavigateTab,
  currencyMode, orders, policy, bdtPerUsd
}) => {
  const order = orders.find((item) => item.id === (currencyMode === 'BDT' ? 'ORD-103' : 'ORD-101') && item.currency === currencyMode);
  const scenarios = refundExamples(order, policy, currencyMode, bdtPerUsd);
  const [activeScenario, setActiveScenario] = useState('normal');
  const [customText, setCustomText] = useState('');
  const selected = scenarios.find((scenario) => scenario.id === activeScenario);
  const ticketText = selected ? selected.text : customText;
  const [scopeOverride, setScopeOverride] = useState<{ enabled: boolean; orderId: string; amount: number; destination: string } | null>(null);
  const scope = scopeOverride ?? {
    enabled: !!selected?.maxAmount && !!order,
    orderId: order?.id ?? '',
    amount: selected?.maxAmount ?? 0,
    destination: order?.original_destination ?? '',
  };

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ currency: typeof currencyMode; trace: AgentTrace } | null>(null);
  const trace = result?.currency === currencyMode ? result.trace : null;
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const [prevCurrencyMode, setPrevCurrencyMode] = useState(currencyMode);
  if (prevCurrencyMode !== currencyMode) {
    setPrevCurrencyMode(currencyMode);
    setScopeOverride(null);
    setResult(null);
    setErrorMsg(null);
  }

  const running = useRef(false);

  const handleRunAgent = async () => {
    if (running.current || unknownAttempt) return;
    running.current = true;
    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);
    let submittedKey: string | null = null;

    try {
      let scopeId: string | undefined = undefined;

      if (scope.enabled) {
        const newScope = await createTaskScope({
          order_id: scope.orderId.trim(),
          allowed_action: 'refund_order',
          max_amount: scope.amount,
          allowed_currency: currencyMode,
          allowed_destination: scope.destination.trim(),
          expires_in_hours: 2,
        });
        scopeId = newScope.scope_id;
      }

      submittedKey = crypto.randomUUID();
      setUnknownAttempt(submittedKey);
      const resultTrace = await processAgentTicket(
        ticketText,
        scopeId,
        submittedKey,
        selected?.maxAmount || undefined,
      );
      setUnknownAttempt(null);
      setResult({ currency: currencyMode, trace: resultTrace });
      onActionComplete();
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      setErrorMsg(/rate limit|too many requests/i.test(detail)
        ? 'Too many requests. Wait a minute and check the result.'
        : submittedKey ? null
        : /^(This order|Payment destination does not match)/.test(detail) ? detail
        : 'Could not set up the request. Check the order, permission and connection, then try again.');
      if (submittedKey) setUnknownAttempt(submittedKey);
    } finally {
      running.current = false;
      setIsLoading(false);
    }
  };

  const handleLookup = async () => {
    if (!unknownAttempt) return;
    setIsChecking(true);
    setLookupMessage(null);
    try {
      const action = await lookupAction(unknownAttempt);
      setLookupMessage(`Recorded status: ${action.status}. Action ID: ${action.action_id || 'N/A'}.`);
      onActionComplete();
    } catch (err) {
      setLookupMessage(err instanceof Error ? err.message : 'Could not check the outcome.');
    } finally {
      setIsChecking(false);
    }
  };


  const parsed = trace?.parsed_parameters;
  const symbol = (parsed?.currency || currencyMode) === 'BDT' ? '৳' : '$';
  const money = (amount: number) => symbol + (amount / 100).toFixed(2);
  const reason = trace?.boundary_reason ?? '';
  const balance = /Requested amount (\d+) exceeds refundable balance (\d+)/.exec(reason);
  const limit = /(?:scope maximum|hard ceiling) (\d+)/.exec(reason);
  let explanation = 'The request did not meet the refund rules. Check the ticket and its refund permission.';
  if (trace?.executed) explanation = 'The demo order balance was reduced.';
  else if (trace?.pending_approval) explanation = 'Review the customer message and the proposed refund before approving. The balance has not changed.';
  else if (reason.includes('REFUND_INTENT_UNCLEAR')) explanation = 'No refund was made. Check the customer’s request and confirm the order, refund amount, and payment destination before trying again.';
  else if (reason.includes('REFUND_AMOUNT_MISMATCH')) explanation = 'The model proposed a different amount from the example. No refund was made.';
  else if (trace?.agent_mode === 'model_not_configured') explanation = 'No AI model is configured. Set the server’s Gemini API key and restart the app.';
  else if (trace?.agent_mode === 'model_failure_fail_closed') explanation = 'The model could not respond. No refund was made. Try again later.';
  else if (trace?.agent_mode === 'invalid_model_output') explanation = 'The model did not return a usable refund request. No refund was made.';
  else if (balance) explanation = 'Only ' + money(Number(balance[2])) + ' is left to refund on this order.';
  else if (limit) explanation = 'The request is above the ' + money(Number(limit[1])) + ' limit.';
  else if (reason.includes('DESTINATION_MISMATCH')) explanation = 'The requested destination does not match the allowed payment account.';
  else if (reason.includes('CURRENCY')) explanation = 'The request uses a different currency from the one allowed.';
  else if (reason.includes('EXPIRED')) explanation = 'Permission for this request has expired. Run the ticket again with fresh permission.';
  else if (/SCOPE_(?:ID_)?REQUIRED/.test(reason) || reason.includes('No trusted task scope')) explanation = 'No refund permission was given. The balance has not changed.';
  else if (!parsed?.order_id || !parsed.amount) explanation = 'No clear refund amount and order were found in the ticket.';
  else if (reason.includes('SCOPE')) explanation = 'The requested order or refund is outside the permission you set.';
  else if (reason.includes('ORDER_NOT_FOUND')) explanation = 'This order was not found in the demo.';
  const status = reason.includes('REFUND_INTENT_UNCLEAR') ? 'Needs clarification' : trace?.executed ? 'Refund recorded' : trace?.pending_approval ? 'Needs approval' : trace?.boundary_verdict === 'ALLOWED' ? 'Allowed by rules' : 'Refund blocked';

  const needsReview = trace?.pending_approval || reason.includes('REFUND_INTENT_UNCLEAR');
  const accepted = trace?.boundary_verdict === 'ALLOWED';
  const StatusIcon = accepted ? CircleCheck : needsReview ? Clock3 : CircleX;
  const statusColor = accepted ? 'border-emerald-600/50 bg-emerald-950/40 text-emerald-300'
    : needsReview ? 'border-amber-600/50 bg-amber-950/40 text-amber-200'
    : 'border-red-600/50 bg-red-950/40 text-red-300';

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-7">
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Test a refund</h1>
        <p className="mt-2 text-sm text-slate-300">Gemini reads the ticket. Refunds within the auto-approve limit pay out automatically; larger ones require your approval.</p>
      </header>
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <section className="min-w-0 rounded-xl border border-borderSubtle bg-surface p-4 sm:p-6" aria-labelledby="ticket-heading">
          <h2 id="ticket-heading" className="mb-4 text-lg font-semibold text-white">Support ticket</h2>
          <fieldset className="space-y-4 disabled:opacity-70" disabled={isLoading || !!unknownAttempt}>
            <label className="block text-sm font-medium">
              Example ticket
              <select className="mt-1 block w-full rounded-lg border border-borderStrong bg-background p-2.5 text-sm text-white"
                value={activeScenario} onChange={(event) => {
                  if (event.target.value === activeScenario) return;
                  setActiveScenario(event.target.value);
                  setScopeOverride(null);
                  setResult(null);
                  setErrorMsg(null);
                }}>
                {scenarios.map((item) => <option key={item.id} value={item.id}>
                  {item.label}{item.amount ? ' (' + item.amount + ')' : item.text ? '' : ' (unavailable)'}
                </option>)}
                <option value="">Custom ticket</option>
              </select>
            </label>
            {selected && !selected.text && <p role="status" className="text-sm text-amber-200">{selected.unavailable}</p>}
            {!selected && !scope.enabled && <p className="text-xs text-slate-400">Set refund permission below to authorize a custom request.</p>}
            <label className="block text-sm font-medium">
              Customer message
              <textarea rows={5} maxLength={10000} value={ticketText}
                onChange={(event) => { setScopeOverride(scope); setCustomText(event.target.value); setActiveScenario(''); setResult(null); setErrorMsg(null); }}
                className="mt-1 block w-full resize-y rounded-lg border border-borderStrong bg-background p-3 text-sm leading-relaxed text-white" />
            </label>
            <div className="rounded-lg border border-borderSubtle bg-background p-3 text-sm">
              <h3 className="font-semibold text-white">Refund permission</h3>
              <p className="mt-1 break-words text-slate-300">{scope.enabled
                ? scope.orderId + ' · Up to ' + currencyMode + ' ' + (scope.amount / 100).toFixed(2) + ' · ' + scope.destination
                : 'No refund permission'}</p>
              <details className="mt-2">
                <summary className="cursor-pointer text-brand-300">Change permission</summary>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="flex items-center gap-2 sm:col-span-2">
                    <input type="checkbox" checked={scope.enabled} onChange={(event) => setScopeOverride({ ...scope, enabled: event.target.checked })} />
                    Give permission for this order
                  </label>
                  <label>Order
                    <input disabled={!scope.enabled} className="mt-1 w-full rounded border border-borderStrong bg-surface p-2" value={scope.orderId}
                      onChange={(event) => setScopeOverride({ ...scope, orderId: event.target.value.toUpperCase() })} />
                  </label>
                  <label>Maximum refund ({currencyMode})
                    <input disabled={!scope.enabled} type="number" min="0.01" step="0.01" className="mt-1 w-full rounded border border-borderStrong bg-surface p-2"
                      value={scope.amount ? scope.amount / 100 : ''} onChange={(event) => setScopeOverride({ ...scope, amount: Math.round(Number(event.target.value) * 100) })} />
                  </label>
                  <label>Payment destination
                    <input disabled={!scope.enabled} className="mt-1 w-full rounded border border-borderStrong bg-surface p-2" value={scope.destination}
                      onChange={(event) => setScopeOverride({ ...scope, destination: event.target.value })} />
                  </label>
                </div>
              </details>
            </div>
            <button type="button" onClick={handleRunAgent} disabled={!ticketText.trim() || (scope.enabled && (!scope.orderId.trim() || !scope.destination.trim() || !Number.isSafeInteger(scope.amount) || scope.amount <= 0))}
              className="rounded-lg bg-brand-400 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-brand-300 disabled:opacity-50">
              {isLoading ? 'Checking…' : 'Run ticket'}
            </button>
          </fieldset>
        </section>
        <section className="min-w-0 rounded-xl border border-borderSubtle bg-surface p-4 sm:p-6" aria-labelledby="result-heading">
          <h2 id="result-heading" className="mb-4 text-lg font-semibold text-white">Refund result</h2>
          {errorMsg && <p role="alert" className="mb-3 break-words text-sm text-red-300">{errorMsg}</p>}
          {unknownAttempt && !isLoading && (
            <div className="space-y-3 text-sm text-amber-200">
              <p>We could not confirm what happened. Check the recorded result before starting another request.</p>
              {lookupMessage && <p role="status" className="break-words">{lookupMessage}</p>}
              <div className="flex flex-wrap gap-3">
                <button className="underline" onClick={handleLookup} disabled={isChecking}>{isChecking ? 'Checking…' : 'Check result'}</button>
                <button className="underline" onClick={() => {
                  if (!window.confirm('Start a new request? The previous request may still finish.')) return;
                  setUnknownAttempt(null); setErrorMsg(null); setLookupMessage(null);
                }}>Start a new request</button>
              </div>
            </div>
          )}
          {isLoading && <p role="status" className="text-sm text-slate-300">Checking the ticket and order…</p>}
          {!trace && !errorMsg && !isLoading && !unknownAttempt && <p className="text-sm text-slate-300">Run the ticket to see the decision here.</p>}
          {trace && (
            <div className="space-y-4">
              <div role="status" className={`rounded-lg border p-4 ${statusColor}`}>
                <h3 className="flex items-center gap-2 font-semibold"><StatusIcon className="h-5 w-5 shrink-0" aria-hidden="true" />{status}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-300">{explanation}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-slate-400">Order</dt><dd>{parsed?.order_id || 'Unknown'}</dd></div>
                <div><dt className="text-slate-400">Requested</dt><dd>{parsed?.amount ? money(parsed.amount) : '—'}</dd></div>
                <div><dt className="text-slate-400">Refund recorded</dt><dd>{trace.refund ? money(trace.refund.amount) : 'None'}</dd></div>
                {trace.agent_mode === 'live_gemini' && <div><dt className="text-slate-400">Read by</dt><dd>Gemini</dd></div>}
              </dl>
              {onNavigateTab && trace.pending_approval && <button className="text-sm font-semibold text-amber-300 underline" onClick={() => onNavigateTab('approvals')}>Open approvals</button>}
              {onNavigateTab && trace.executed && <button className="text-sm font-semibold text-brand-300 underline" onClick={() => onNavigateTab('sandbox')}>See order balance</button>}
              <details className="border-t border-borderSubtle pt-3 text-sm">
                <summary className="cursor-pointer text-slate-300">Technical details</summary>
                <ol className="mt-3 space-y-3 break-words">
                  {trace.pipeline_stages?.map((stage) => <li key={stage.id}><strong>{stage.name}</strong><p className="text-slate-400">{stage.details}</p></li>)}
                </ol>
              </details>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
