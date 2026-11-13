import React, { useState } from 'react';
import type { PolicyConfig } from '../types';
import { updatePolicy, type fetchExchangeRate } from '../api';
import { formatPolicyLimit } from '../policyMoney';
import { Sliders, Save, CheckCircle2, ShieldCheck, AlertOctagon } from 'lucide-react';

interface PolicyManagerProps {
  policy: PolicyConfig;
  currencyMode: 'USD' | 'BDT';
  quote: Awaited<ReturnType<typeof fetchExchangeRate>> | null;
  onPolicyUpdated: (updated: PolicyConfig) => void;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ policy, currencyMode, quote, onPolicyUpdated }) => {
  const [autoAllow, setAutoAllow] = useState(String(policy.auto_allow_threshold / 100));
  const [hardCeiling, setHardCeiling] = useState(String(policy.hard_ceiling_threshold / 100));
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [prevThresholds, setPrevThresholds] = useState({
    auto: policy.auto_allow_threshold,
    ceiling: policy.hard_ceiling_threshold,
  });

  if (
    prevThresholds.auto !== policy.auto_allow_threshold ||
    prevThresholds.ceiling !== policy.hard_ceiling_threshold
  ) {
    setPrevThresholds({
      auto: policy.auto_allow_threshold,
      ceiling: policy.hard_ceiling_threshold,
    });
    setAutoAllow(String(policy.auto_allow_threshold / 100));
    setHardCeiling(String(policy.hard_ceiling_threshold / 100));
  }

  const [saveError, setSaveError] = useState<string | null>(null);
  const toMinorUnits = (value: string) => /^\d+(?:\.\d{1,2})?$/.test(value) ? Math.round(Number(value) * 100) : NaN;
  const autoAmount = toMinorUnits(autoAllow);
  const maximumAmount = toMinorUnits(hardCeiling);
  const validAmounts = [autoAmount, maximumAmount].every((amount) => Number.isSafeInteger(amount) && amount > 0);
  const inputError = !validAmounts
    ? 'Enter positive amounts with up to two decimal places.'
    : autoAmount > maximumAmount ? 'The auto-approve limit must be at or below the maximum refund.' : null;

  const handleSave = async () => {
    if (inputError) return;
    setSaveError(null);
    setIsSaving(true);
    setSavedSuccess(false);
    try {
      const updated = await updatePolicy({
        auto_allow_threshold: autoAmount,
        hard_ceiling_threshold: maximumAmount
      });
      onPolicyUpdated(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch {
      setSaveError('Could not save the refund rules. Check the connection and try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Intro Header */}
      <div className="bg-surface rounded-xl border border-borderSubtle p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sliders className="w-5 h-5 text-brand-400" />
              <h1 className="text-base font-bold text-white">
                Refund rules
              </h1>
            </div>
            <p className="text-sm text-slate-400">
              Rules are set in USD. For BDT refunds, the server applies the USD limits at its latest available exchange rate.
            </p>
          </div>
          <span className="self-start sm:self-auto text-xs font-mono px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/30 text-brand-400 font-semibold">
            Rule Version: {policy.version}
          </span>
        </div>
        {currencyMode === 'BDT' && (
          <p role="status" className="mb-5 text-xs text-slate-300">
            {quote
              ? <>1 USD = {quote.bdt_per_usd} BDT · {quote.as_of} · {quote.source === 'bangladesh_bank' ? 'Bangladesh Bank reference' : quote.stale ? 'Last available quote' : 'ExchangeRate-API'}</>
              : 'BDT rate unavailable in this view. You can still edit the USD limits.'}
          </p>
        )}

        {savedSuccess && (
          <div role="status" aria-live="polite" className="p-3 mb-4 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-xs text-emerald-300 flex items-center gap-2 font-mono">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Refund rules saved.</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
          {/* 1. Auto-Approve Threshold Card */}
          <div className="rule-card [--rule-accent:#34d399] flex flex-col p-5 rounded-xl bg-background border border-borderSubtle gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-semibold text-white">Auto-Approve Limit ({currencyMode})</span>
              </div>
            </div>
            <p className="rule-amount text-2xl sm:text-3xl tracking-tight font-semibold text-emerald-300 break-all">
              {formatPolicyLimit(policy.auto_allow_threshold, currencyMode, quote?.bdt_per_usd) ?? '—'}
            </p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Within this limit, requests that pass scope and balance checks can execute automatically. Larger eligible requests need operator approval.
            </p>
            <label className="mt-auto grid gap-1.5 text-xs text-slate-300">
              Edit auto-approve limit (USD)
              <input
              type="text"
              inputMode="decimal"
              value={autoAllow}
              onChange={(event) => { setAutoAllow(event.target.value); setSavedSuccess(false); setSaveError(null); }}
              className="w-full rounded-lg border border-borderStrong bg-surface p-2.5 text-sm text-white"
              />
            </label>
          </div>

          {/* 2. Hard Ceiling Card */}
          <div className="rule-card [--rule-accent:#fb7185] flex flex-col p-5 rounded-xl bg-background border border-borderSubtle gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 text-red-400" />
                <span className="text-sm font-semibold text-white">Maximum refund ({currencyMode})</span>
              </div>
            </div>
            <p className="rule-amount text-2xl sm:text-3xl tracking-tight font-semibold text-rose-300 break-all">
              {formatPolicyLimit(policy.hard_ceiling_threshold, currencyMode, quote?.bdt_per_usd) ?? '—'}
            </p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Requests above this amount are blocked.
            </p>
            <label className="mt-auto grid gap-1.5 text-xs text-slate-300">
              Edit maximum refund (USD)
              <input
              type="text"
              inputMode="decimal"
              value={hardCeiling}
              onChange={(event) => { setHardCeiling(event.target.value); setSavedSuccess(false); setSaveError(null); }}
              className="w-full rounded-lg border border-borderStrong bg-surface p-2.5 text-sm text-white"
              />
            </label>
          </div>
        </div>

        {(inputError || saveError) && <p role="alert" className="mt-4 text-sm text-red-300">{inputError || saveError}</p>}

        {/* Save Changes Button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving || !!inputError}
            className="px-5 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs flex items-center gap-2 transition disabled:opacity-50 shadow-sm"
          >
            <Save className="w-4 h-4" />
            <span>{isSaving ? 'Saving Changes...' : 'Save Policy Changes'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
