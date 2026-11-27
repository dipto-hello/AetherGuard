import React, { useRef, useState } from 'react';
import { CircleCheck, CircleX, Clock3, MessageSquareText, ReceiptText, ImagePlus, CreditCard, Send } from 'lucide-react';
import type { AgentTrace, Order, PolicyConfig } from '../types';
import { refundExamples } from '../refundExamples';
import { formatMinor } from '../policyMoney';
import { processAgentTicket, lookupAction } from '../api';
import { statusLabel, type MyRequest } from '../myRequests';

interface AgentArenaProps {
  onActionComplete: () => void;
  unknownAttempt: string | null;
  setUnknownAttempt: (key: string | null) => void;
  onRequestRecorded?: (request: MyRequest) => void;
  orders: Order[];
  policy: PolicyConfig | null;
}

// Server rejections that happen before anything is recorded, so the request is definitely not in flight.
const DEFINITE_REJECTION = /^(This order|Choose the order|Refund permission is set)/;

export const AgentArena: React.FC<AgentArenaProps> = ({
  onActionComplete,
  unknownAttempt,
  setUnknownAttempt,
  onRequestRecorded,
  orders, policy
}) => {
  const scenarios = refundExamples(orders, policy);
  const [activeScenario, setActiveScenario] = useState('normal');
  const [customText, setCustomText] = useState('');
  const selected = scenarios.find((scenario) => scenario.id === activeScenario);
  const ticketText = selected ? selected.text : customText;
  // Only the order is chosen here; the server sets the refund limit and destination from its record.
  const [orderOverride, setOrderOverride] = useState<string | null>(null);
  const refundableOrders = orders.filter((o) => o.currency === 'BDT' && o.refundable_amount > 0);
  const orderId = orderOverride ?? selected?.order?.id ?? '';
  const chosenOrder = refundableOrders.find((o) => o.id === orderId);

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
      setErrorMsg('We could not read that photo. Please use a JPEG, PNG or WebP image.');
    }
  };

  const handleRunAgent = async () => {
    if (running.current || unknownAttempt || !chosenOrder) return;
    running.current = true;
    setIsLoading(true);
    setErrorMsg(null);
    setResult(null);
    const submittedKey = crypto.randomUUID();
    setUnknownAttempt(submittedKey);

    try {
      const resultTrace = await processAgentTicket(
        ticketText,
        chosenOrder.id,
        submittedKey,
        selected?.maxAmount || undefined,
        evidence ? { data: evidence.data, mimeType: evidence.mimeType } : undefined,
      );
      setUnknownAttempt(null);
      setResult(resultTrace);
      if (resultTrace.pending_approval || resultTrace.executed) {
        onRequestRecorded?.({
          key: submittedKey,
          orderId: resultTrace.parsed_parameters?.order_id || chosenOrder.id,
          amount: resultTrace.parsed_parameters?.amount ?? 0,
          status: resultTrace.executed ? 'executed' : 'pending',
        });
      }
      onActionComplete();
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      if (DEFINITE_REJECTION.test(detail)) {
        setUnknownAttempt(null);
        setErrorMsg(detail);
      } else if (/rate limit|too many requests/i.test(detail)) {
        setErrorMsg('Too many requests. Please wait a minute, then check the status.');
      }
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
      setLookupMessage(`Your request status: ${statusLabel(action.status)}.`);
      onActionComplete();
    } catch (err) {
      setLookupMessage(/not found/i.test(err instanceof Error ? err.message : '')
        ? 'We have no record of that request, so nothing was refunded.'
        : 'We could not check the status. Please try again.');
    } finally {
      setIsChecking(false);
    }
  };


  const parsed = trace?.parsed_parameters;
  const money = (amount: number) => formatMinor(BigInt(amount), parsed?.currency || 'BDT');
  const reason = trace?.boundary_reason ?? '';
  const balance = /Requested amount (\d+) exceeds refundable balance (\d+)/.exec(reason);
  const limit = /(?:scope maximum|hard ceiling) (\d+)/.exec(reason);
  let explanation = 'We could not approve this refund. Nothing was refunded.';
  const judgeReason = (trace?.claim_judgment?.reason ?? '').replace(/\.$/, '');
  const judgeInvalid = reason.startsWith('CLAIM_INVALID');
  const judgeUnsure = reason.startsWith('CLAIM_NEEDS_REVIEW');
  if (trace?.executed && trace.refund) {
    // order_state holds the balance read before this refund was written.
    const left = trace.order_state ? trace.order_state.refundable_amount - trace.refund.amount : null;
    explanation = money(trace.refund.amount) + ' is on its way back to ' + trace.refund.destination + '.'
      + (left !== null ? ' ' + money(left) + ' can still be refunded on ' + trace.refund.order_id + '.' : '');
  }
  else if (trace?.executed) explanation = 'Your refund has been approved.';
  else if (judgeInvalid) explanation = 'We could not approve this claim: ' + judgeReason + '. Nothing was refunded.';
  else if (judgeUnsure || trace?.pending_approval) explanation = 'A member of our team will review your request. You can follow it under My requests below. Nothing has been refunded yet.';
  else if (reason.includes('REFUND_INTENT_UNCLEAR')) explanation = 'We could not tell which order, amount or payment account you meant. Please mention the order number and the amount you want back.';
  else if (reason.includes('REFUND_AMOUNT_MISMATCH')) explanation = 'We read a different amount from the one in your message. Nothing was refunded. Please try again.';
  else if (trace?.agent_mode === 'model_not_configured' || trace?.agent_mode === 'model_failure_fail_closed' || trace?.agent_mode === 'invalid_model_output')
    explanation = 'Our refund assistant is unavailable right now. Nothing was refunded. Please try again later.';
  else if (balance) explanation = 'Only ' + money(Number(balance[2])) + ' can still be refunded on this order.';
  else if (limit) explanation = 'This is more than we can refund online (' + money(Number(limit[1])) + ' maximum). Please contact support.';
  else if (reason.includes('DESTINATION_MISMATCH')) explanation = 'Refunds can only go back to the payment method you used for this order.';
  else if (reason.includes('CURRENCY')) explanation = 'Only taka (BDT) refunds are supported.';
  else if (reason.includes('EXPIRED')) explanation = 'Your request timed out. Please send it again.';
  else if (!parsed?.order_id || !parsed.amount) explanation = 'We could not find an order number and refund amount in your message.';
  else if (reason.includes('SCOPE')) explanation = 'Your message does not match the order you selected. Check the order number and amount.';
  else if (reason.includes('ORDER_NOT_FOUND')) explanation = 'We could not find this order.';
  const needsReview = trace?.pending_approval || judgeUnsure;
  const unclear = reason.includes('REFUND_INTENT_UNCLEAR');
  const accepted = trace?.boundary_verdict === 'ALLOWED';
  const status = trace?.executed || accepted ? 'Refund approved' : needsReview ? 'Under review' : unclear ? 'We need more details' : 'Refund declined';
  const StatusIcon = accepted ? CircleCheck : needsReview || unclear ? Clock3 : CircleX;
  const statusColor = accepted ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : needsReview || unclear ? 'border-amber-200 bg-amber-50 text-amber-900'
    : 'border-red-200 bg-red-50 text-red-800';

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-7">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Request a refund</h1>
        <p className="mt-2 max-w-2xl text-base leading-relaxed text-slate-600">Tell us what went wrong with your order. Small refunds are approved straight away; larger ones are checked by our team first.</p>
      </header>
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <section className="user-card min-w-0 p-5 sm:p-6" aria-labelledby="ticket-heading">
          <h2 id="ticket-heading" className="mb-5 flex items-center gap-2 text-lg font-semibold text-slate-900"><MessageSquareText className="h-5 w-5 text-emerald-600" aria-hidden="true" />Your request</h2>
          <fieldset className="space-y-5 disabled:opacity-70" disabled={isLoading || !!unknownAttempt}>
            <label className="block text-sm font-semibold text-slate-800">
              Start from an example
              <select className="user-field cursor-pointer"
                value={activeScenario} onChange={(event) => {
                  if (event.target.value === activeScenario) return;
                  setActiveScenario(event.target.value);
                  setOrderOverride(null);
                  setEvidence(null);
                  setResult(null);
                  setErrorMsg(null);
                }}>
                {scenarios.map((item) => <option key={item.id} value={item.id}>
                  {item.label}{item.amount ? ' (' + item.amount + ')' : item.text ? '' : ' (unavailable)'}
                </option>)}
                <option value="">Write my own</option>
              </select>
            </label>
            {selected && !selected.text && <p role="status" className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">{selected.unavailable}</p>}
            <div>
              <label className="block text-sm font-semibold text-slate-800">
                Order
                <select className="user-field cursor-pointer" value={chosenOrder ? orderId : ''}
                  onChange={(event) => { setOrderOverride(event.target.value); setCustomText(ticketText); setActiveScenario(''); setResult(null); setErrorMsg(null); }}>
                  <option value="" disabled>Choose your order</option>
                  {refundableOrders.map((o) => <option key={o.id} value={o.id}>
                    {o.id} · {formatMinor(BigInt(o.refundable_amount))} refundable
                  </option>)}
                </select>
              </label>
              {chosenOrder && (
                <p className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-600">
                  <CreditCard className="h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />
                  Refunds go back to <span className="font-semibold text-slate-800">{chosenOrder.original_destination}</span>
                </p>
              )}
            </div>
            <label className="block text-sm font-semibold text-slate-800">
              Your message
              <textarea rows={5} maxLength={10000} value={ticketText} placeholder="Example: My order ORD-103 arrived damaged. Please refund ৳500."
                onChange={(event) => { setOrderOverride(orderId); setCustomText(event.target.value); setActiveScenario(''); setResult(null); setErrorMsg(null); }}
                className="user-field resize-y leading-relaxed" />
            </label>
            <div className="text-sm">
              <label className="block font-semibold text-slate-800">
                <span className="flex items-center gap-1.5"><ImagePlus className="h-4 w-4 text-slate-500" aria-hidden="true" />Photo of the problem <span className="font-normal text-slate-500">(optional)</span></span>
                <input key={evidence ? 'set' : 'empty'} type="file" accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => handlePhoto(event.target.files?.[0])}
                  className="mt-1.5 block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 p-2 text-sm text-slate-600 file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-emerald-600 file:px-3 file:py-1.5 file:font-semibold file:text-white hover:file:bg-emerald-700" />
              </label>
              {evidence && (
                <div className="mt-2 flex items-center gap-3">
                  <img src={evidence.preview} alt="Photo preview" className="h-16 w-16 rounded-lg border border-slate-200 object-cover" />
                  <button type="button" className="user-link text-sm" onClick={() => setEvidence(null)}>Remove photo</button>
                </div>
              )}
              <p className="mt-1.5 text-sm text-slate-500">A photo helps us check your claim faster. This is a demo, so please use sample photos only.</p>
            </div>
            <button type="button" onClick={handleRunAgent} disabled={!ticketText.trim() || !chosenOrder}
              className="user-cta w-full sm:w-auto">
              <Send className="h-4 w-4" aria-hidden="true" />
              {isLoading ? 'Submitting…' : 'Submit request'}
            </button>
          </fieldset>
        </section>
        <section className="user-card min-w-0 p-5 sm:p-6 lg:sticky lg:top-24" aria-labelledby="result-heading">
          <h2 id="result-heading" className="mb-5 flex items-center gap-2 text-lg font-semibold text-slate-900"><ReceiptText className="h-5 w-5 text-emerald-600" aria-hidden="true" />Request status</h2>
          {errorMsg && <p role="alert" className="mb-3 break-words rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{errorMsg}</p>}
          {unknownAttempt && !isLoading && (
            <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <p>We could not confirm whether your request went through. Please check its status before sending another one.</p>
              {lookupMessage && <p role="status" className="break-words">{lookupMessage}</p>}
              <div className="flex flex-wrap gap-3">
                <button className="user-link" onClick={handleLookup} disabled={isChecking}>{isChecking ? 'Checking…' : 'Check status'}</button>
                <button className="user-link" onClick={() => {
                  if (!window.confirm('Send a new request? The previous one may still go through.')) return;
                  setUnknownAttempt(null); setErrorMsg(null); setLookupMessage(null);
                }}>Send a new request</button>
              </div>
            </div>
          )}
          {isLoading && <p role="status" className="flex items-center gap-2 text-sm text-slate-600"><Clock3 className="h-4 w-4 animate-pulse text-emerald-600" aria-hidden="true" />Checking your request…</p>}
          {!trace && !errorMsg && !isLoading && !unknownAttempt && <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500"><ReceiptText className="mx-auto mb-2 h-8 w-8 text-slate-400" aria-hidden="true" />Submit your request to see the result here.</div>}
          {trace && (
            <div className="space-y-4">
              <div role="status" className={`rounded-xl border p-4 ${statusColor}`}>
                <h3 className="flex items-center gap-2 font-semibold"><StatusIcon className="h-5 w-5 shrink-0" aria-hidden="true" />{status}</h3>
                <p className="mt-1 text-sm leading-relaxed text-slate-700">{explanation}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm [&>div]:rounded-lg [&>div]:bg-slate-50 [&>div]:p-3 [&_dd]:mt-0.5 [&_dd]:font-semibold [&_dd]:text-slate-900">
                <div><dt className="text-slate-500">Order</dt><dd>{parsed?.order_id || chosenOrder?.id || '—'}</dd></div>
                <div><dt className="text-slate-500">Amount requested</dt><dd>{parsed?.amount ? money(parsed.amount) : '—'}</dd></div>
                <div><dt className="text-slate-500">Amount refunded</dt><dd>{trace.refund ? money(trace.refund.amount) : 'None yet'}</dd></div>
              </dl>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
