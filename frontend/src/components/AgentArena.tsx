import React, { useRef, useState } from 'react';
import { CircleCheck, CircleX, Clock3, MessageSquareText, ReceiptText, ImagePlus, ShieldCheck, Send } from 'lucide-react';
import type { AgentTrace, Order, PolicyConfig } from '../types';
import { refundExamples } from '../refundExamples';
import { formatMinor } from '../policyMoney';
import { processAgentTicket, createTaskScope, lookupAction } from '../api';
import type { MyRequest } from '../myRequests';

interface AgentArenaProps {
  onActionComplete: () => void;
  unknownAttempt: string | null;
  setUnknownAttempt: (key: string | null) => void;
  onNavigateTab?: (tab: string) => void;
  onRequestRecorded?: (request: MyRequest) => void;
  orders: Order[];
  policy: PolicyConfig | null;
}

export const AgentArena: React.FC<AgentArenaProps> = ({
  onActionComplete,
  unknownAttempt,
  setUnknownAttempt,
  onNavigateTab,
  onRequestRecorded,
  orders, policy
}) => {
  const scenarios = refundExamples(orders, policy);
  const [activeScenario, setActiveScenario] = useState('normal');
  const [customText, setCustomText] = useState('');
  const selected = scenarios.find((scenario) => scenario.id === activeScenario);
  const ticketText = selected ? selected.text : customText;
  const order = selected?.order;
  const [scopeOverride, setScopeOverride] = useState<{ enabled: boolean; orderId: string; amount: number; destination: string } | null>(null);
  const scope = scopeOverride ?? {
    enabled: !!selected?.maxAmount && !!order,
    orderId: order?.id ?? '',
    amount: selected?.maxAmount ?? 0,
    destination: order?.original_destination ?? '',
  };

  const [evidence, setEvidence] = useState<{ data: string; mimeType: string; preview: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [trace, setResult] = useState<AgentTrace | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const running = useRef(false);

  // Shrink the photo in the browser so the request stays under the server's 1 MB limit.
  const handlePhoto = async (file: File | undefined) => {
    setEvidence(null);
    if (!file) return;
    try {
      const bitmap = await createImageBitmap(file);
      const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      const preview = canvas.toDataURL('image/jpeg', 0.8);
      setEvidence({ data: preview.slice(preview.indexOf(',') + 1), mimeType: 'image/jpeg', preview });
      setResult(null);
      setErrorMsg(null);
    } catch {
      setErrorMsg('Could not read that photo. Use a JPEG, PNG or WebP image.');
    }
  };

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
          allowed_currency: 'BDT',
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
        evidence ? { data: evidence.data, mimeType: evidence.mimeType } : undefined,
      );
      setUnknownAttempt(null);
      setResult(resultTrace);
      if (resultTrace.pending_approval || resultTrace.executed) {
        onRequestRecorded?.({
          key: submittedKey,
          orderId: resultTrace.parsed_parameters?.order_id || 'Unknown order',
          amount: resultTrace.parsed_parameters?.amount ?? 0,
          status: resultTrace.executed ? 'executed' : 'pending',
        });
      }
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
  const money = (amount: number) => formatMinor(BigInt(amount), parsed?.currency || 'BDT');
  const reason = trace?.boundary_reason ?? '';
  const balance = /Requested amount (\d+) exceeds refundable balance (\d+)/.exec(reason);
  const limit = /(?:scope maximum|hard ceiling) (\d+)/.exec(reason);
  let explanation = 'The request did not meet the refund rules. Check the ticket and its refund permission.';
  const judgeReason = (trace?.claim_judgment?.reason ?? '').replace(/\.$/, '');
  const judgeInvalid = reason.startsWith('CLAIM_INVALID');
  const judgeUnsure = reason.startsWith('CLAIM_NEEDS_REVIEW');
  if (trace?.executed && trace.refund) {
    // order_state holds the balance read before this refund was written.
    const left = trace.order_state ? trace.order_state.refundable_amount - trace.refund.amount : null;
    explanation = money(trace.refund.amount) + ' refunded to ' + trace.refund.destination + '.'
      + (left !== null ? ' ' + trace.refund.order_id + ' now has ' + money(left) + ' left to refund.' : '');
  }
  else if (trace?.executed) explanation = 'The order balance was reduced.';
  else if (judgeInvalid) explanation = 'The AI judge found this claim invalid: ' + judgeReason + '. No refund was made.';
  else if (judgeUnsure) explanation = 'The AI judge was unsure: ' + judgeReason + '. Approve or reject this refund in Approvals. The balance has not changed.';
  else if (trace?.pending_approval) explanation = 'Waiting for admin approval. The balance has not changed.';
  else if (reason.includes('REFUND_INTENT_UNCLEAR')) explanation = 'No refund was made. Check the customer’s request and confirm the order, refund amount, and payment destination before trying again.';
  else if (reason.includes('REFUND_AMOUNT_MISMATCH')) explanation = 'The model proposed a different amount from the example. No refund was made.';
  else if (trace?.agent_mode === 'model_not_configured') explanation = 'No AI model is configured. Set the server’s Gemini API key and restart the app.';
  else if (trace?.agent_mode === 'model_failure_fail_closed') explanation = 'The model could not respond. No refund was made. Try again later.';
  else if (trace?.agent_mode === 'invalid_model_output') explanation = 'The model did not return a usable refund request. No refund was made.';
  else if (balance) explanation = 'Only ' + money(Number(balance[2])) + ' is left to refund on this order.';
  else if (limit) explanation = 'The request is above the ' + money(Number(limit[1])) + ' limit.';
  else if (reason.includes('DESTINATION_MISMATCH')) explanation = 'The requested destination does not match the allowed payment account.';
  else if (reason.includes('CURRENCY')) explanation = 'Only taka (BDT) refunds are supported.';
  else if (reason.includes('EXPIRED')) explanation = 'Permission for this request has expired. Run the ticket again with fresh permission.';
  else if (/SCOPE_(?:ID_)?REQUIRED/.test(reason) || reason.includes('No trusted task scope')) explanation = 'No refund permission was given. The balance has not changed.';
  else if (!parsed?.order_id || !parsed.amount) explanation = 'No clear refund amount and order were found in the ticket.';
  else if (reason.includes('SCOPE')) explanation = 'The requested order or refund is outside the permission you set.';
  else if (reason.includes('ORDER_NOT_FOUND')) explanation = 'This order was not found.';
  const status = judgeInvalid ? 'Refund blocked by AI judge' : reason.includes('REFUND_INTENT_UNCLEAR') ? 'Needs clarification' : trace?.executed ? 'Refund recorded' : trace?.pending_approval ? 'Needs approval' : trace?.boundary_verdict === 'ALLOWED' ? 'Allowed by rules' : 'Refund blocked';

  const needsReview = trace?.pending_approval || reason.includes('REFUND_INTENT_UNCLEAR');
  const accepted = trace?.boundary_verdict === 'ALLOWED';
  const StatusIcon = accepted ? CircleCheck : needsReview ? Clock3 : CircleX;
  const statusColor = accepted ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : needsReview ? 'border-amber-200 bg-amber-50 text-amber-900'
    : 'border-red-200 bg-red-50 text-red-800';

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-7">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Request a refund</h1>
        <p className="mt-2 max-w-2xl text-base leading-relaxed text-slate-600">Gemini reads the ticket. Refunds within the auto-approve limit pay out automatically; larger ones require your approval.</p>
      </header>
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <section className="user-card min-w-0 p-5 sm:p-6" aria-labelledby="ticket-heading">
          <h2 id="ticket-heading" className="mb-5 flex items-center gap-2 text-lg font-semibold text-slate-900"><MessageSquareText className="h-5 w-5 text-emerald-600" aria-hidden="true" />Support ticket</h2>
          <fieldset className="space-y-5 disabled:opacity-70" disabled={isLoading || !!unknownAttempt}>
            <label className="block text-sm font-semibold text-slate-800">
              Example ticket
              <select className="user-field cursor-pointer"
                value={activeScenario} onChange={(event) => {
                  if (event.target.value === activeScenario) return;
                  setActiveScenario(event.target.value);
                  setScopeOverride(null);
                  setEvidence(null);
                  setResult(null);
                  setErrorMsg(null);
                }}>
                {scenarios.map((item) => <option key={item.id} value={item.id}>
                  {item.label}{item.amount ? ' (' + item.amount + ')' : item.text ? '' : ' (unavailable)'}
                </option>)}
                <option value="">Custom ticket</option>
              </select>
            </label>
            {selected && !selected.text && <p role="status" className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">{selected.unavailable}</p>}
            {!selected && !scope.enabled && <p className="text-sm text-slate-500">Set refund permission below to authorize a custom request.</p>}
            <label className="block text-sm font-semibold text-slate-800">
              Customer message
              <textarea rows={5} maxLength={10000} value={ticketText}
                onChange={(event) => { setScopeOverride(scope); setCustomText(event.target.value); setActiveScenario(''); setResult(null); setErrorMsg(null); }}
                className="user-field resize-y leading-relaxed" />
            </label>
            <div className="text-sm">
              <label className="block font-semibold text-slate-800">
                <span className="flex items-center gap-1.5"><ImagePlus className="h-4 w-4 text-slate-500" aria-hidden="true" />Evidence photo <span className="font-normal text-slate-500">(optional)</span></span>
                <input key={evidence ? 'set' : 'empty'} type="file" accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => handlePhoto(event.target.files?.[0])}
                  className="mt-1.5 block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 p-2 text-sm text-slate-600 file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-emerald-600 file:px-3 file:py-1.5 file:font-semibold file:text-white hover:file:bg-emerald-700" />
              </label>
              {evidence && (
                <div className="mt-2 flex items-center gap-3">
                  <img src={evidence.preview} alt="Evidence photo preview" className="h-16 w-16 rounded-lg border border-slate-200 object-cover" />
                  <button type="button" className="user-link text-sm" onClick={() => setEvidence(null)}>Remove photo</button>
                </div>
              )}
              <p className="mt-1.5 text-sm text-slate-500">The AI judge reviews the message and photo before any refund rule runs. Use synthetic photos only.</p>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-sm">
              <h3 className="flex items-center gap-1.5 font-semibold text-slate-900"><ShieldCheck className="h-4 w-4 text-emerald-700" aria-hidden="true" />Refund permission</h3>
              <p className="mt-1 break-words text-slate-700">{scope.enabled
                ? scope.orderId + ' · Up to ' + formatMinor(BigInt(scope.amount)) + ' · ' + scope.destination
                : 'No refund permission'}</p>
              <details className="mt-2">
                <summary className="user-link inline-block">Change permission</summary>
                <div className="mt-3 grid gap-3 text-slate-800 sm:grid-cols-2">
                  <label className="flex items-center gap-2 sm:col-span-2">
                    <input type="checkbox" className="h-4 w-4 accent-emerald-600" checked={scope.enabled} onChange={(event) => setScopeOverride({ ...scope, enabled: event.target.checked })} />
                    Give permission for this order
                  </label>
                  <label>Order
                    <input disabled={!scope.enabled} className="user-field" value={scope.orderId}
                      onChange={(event) => setScopeOverride({ ...scope, orderId: event.target.value.toUpperCase() })} />
                  </label>
                  <label>Maximum refund (BDT)
                    <input disabled={!scope.enabled} type="number" min="0.01" step="0.01" className="user-field"
                      value={scope.amount ? scope.amount / 100 : ''} onChange={(event) => setScopeOverride({ ...scope, amount: Math.round(Number(event.target.value) * 100) })} />
                  </label>
                  <label>Payment destination
                    <input disabled={!scope.enabled} className="user-field" value={scope.destination}
                      onChange={(event) => setScopeOverride({ ...scope, destination: event.target.value })} />
                  </label>
                </div>
              </details>
            </div>
            <button type="button" onClick={handleRunAgent} disabled={!ticketText.trim() || (scope.enabled && (!scope.orderId.trim() || !scope.destination.trim() || !Number.isSafeInteger(scope.amount) || scope.amount <= 0))}
              className="user-cta w-full sm:w-auto">
              <Send className="h-4 w-4" aria-hidden="true" />
              {isLoading ? 'Checking…' : 'Run ticket'}
            </button>
          </fieldset>
        </section>
        <section className="user-card min-w-0 p-5 sm:p-6 lg:sticky lg:top-24" aria-labelledby="result-heading">
          <h2 id="result-heading" className="mb-5 flex items-center gap-2 text-lg font-semibold text-slate-900"><ReceiptText className="h-5 w-5 text-emerald-600" aria-hidden="true" />Refund result</h2>
          {errorMsg && <p role="alert" className="mb-3 break-words rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{errorMsg}</p>}
          {unknownAttempt && !isLoading && (
            <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <p>We could not confirm what happened. Check the recorded result before starting another request.</p>
              {lookupMessage && <p role="status" className="break-words">{lookupMessage}</p>}
              <div className="flex flex-wrap gap-3">
                <button className="user-link" onClick={handleLookup} disabled={isChecking}>{isChecking ? 'Checking…' : 'Check result'}</button>
                <button className="user-link" onClick={() => {
                  if (!window.confirm('Start a new request? The previous request may still finish.')) return;
                  setUnknownAttempt(null); setErrorMsg(null); setLookupMessage(null);
                }}>Start a new request</button>
              </div>
            </div>
          )}
          {isLoading && <p role="status" className="flex items-center gap-2 text-sm text-slate-600"><Clock3 className="h-4 w-4 animate-pulse text-emerald-600" aria-hidden="true" />Checking the ticket and order…</p>}
          {!trace && !errorMsg && !isLoading && !unknownAttempt && <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500"><ReceiptText className="mx-auto mb-2 h-8 w-8 text-slate-400" aria-hidden="true" />Run the ticket to see the decision here.</div>}
          {trace && (
            <div className="space-y-4">
              <div role="status" className={`rounded-xl border p-4 ${statusColor}`}>
                <h3 className="flex items-center gap-2 font-semibold"><StatusIcon className="h-5 w-5 shrink-0" aria-hidden="true" />{status}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-700">{explanation}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm [&>div]:rounded-lg [&>div]:bg-slate-50 [&>div]:p-3 [&_dd]:mt-0.5 [&_dd]:font-semibold [&_dd]:text-slate-900">
                <div><dt className="text-slate-500">Order</dt><dd>{parsed?.order_id || 'Unknown'}</dd></div>
                <div><dt className="text-slate-500">Requested</dt><dd>{parsed?.amount ? money(parsed.amount) : '—'}</dd></div>
                <div><dt className="text-slate-500">Refund recorded</dt><dd>{trace.refund ? money(trace.refund.amount) : 'None'}</dd></div>
                {trace.claim_judgment && <div><dt className="text-slate-500">AI judge</dt><dd className="capitalize">{trace.claim_judgment.verdict}</dd></div>}
                {trace.agent_mode === 'live_gemini' && <div><dt className="text-slate-500">Read by</dt><dd>Gemini</dd></div>}
              </dl>
              {onNavigateTab && trace.pending_approval && <button className="user-link text-sm" onClick={() => onNavigateTab('approvals')}>Open approvals</button>}
              {onNavigateTab && trace.executed && <button className="user-link text-sm" onClick={() => onNavigateTab('sandbox')}>See order balance</button>}
              <details className="border-t border-slate-200 pt-3 text-sm">
                <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-900">Technical details</summary>
                <ol className="mt-3 space-y-3 break-words">
                  {trace.pipeline_stages?.map((stage) => <li key={stage.id}><strong className="text-slate-800">{stage.name}</strong><p className="text-slate-500">{stage.details}</p></li>)}
                </ol>
              </details>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
