import React, { useState, useEffect } from 'react';
import type { PolicyConfig } from '../types';
import { updatePolicy } from '../api';
import { Sliders, Save, CheckCircle2 } from 'lucide-react';

interface PolicyManagerProps {
  policy: PolicyConfig;
  onPolicyUpdated: (updated: PolicyConfig) => void;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ policy, onPolicyUpdated }) => {
  const [autoAllow, setAutoAllow] = useState<number>(policy.auto_allow_threshold / 100);
  const [hardCeiling, setHardCeiling] = useState<number>(policy.hard_ceiling_threshold / 100);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  useEffect(() => {
    setAutoAllow(policy.auto_allow_threshold / 100);
    setHardCeiling(policy.hard_ceiling_threshold / 100);
  }, [policy.auto_allow_threshold, policy.hard_ceiling_threshold]);

  const handleSave = async () => {
    setIsSaving(true);
    setSavedSuccess(false);
    try {
      const updated = await updatePolicy({
        auto_allow_threshold: autoAllow * 100,
        hard_ceiling_threshold: hardCeiling * 100
      });
      onPolicyUpdated(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch {
      alert('Failed to update policy');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-surface rounded border border-borderSubtle p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-inkPrimary flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-inkMuted" />
              <span>Deterministic Execution Firewall Rules</span>
            </h2>
            <p className="text-xs text-inkMuted">
              Thresholds are in major currency units and currently use the same numeric limits for each currency.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surfaceCard border border-borderSubtle text-emerald-400">
            Deterministic Engine
          </span>
        </div>

        {savedSuccess && (
          <div className="p-3 mb-3 rounded bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-300 flex items-center gap-2 font-mono">
            <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Policy thresholds updated.</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {/* Auto-Allow Threshold */}
          <div className="p-3.5 rounded bg-background border border-borderSubtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200">Auto-Allow Threshold</span>
              <span className="text-sm font-mono font-semibold text-emerald-400">{autoAllow.toFixed(2)} units</span>
            </div>
            <p className="text-[11px] text-inkMuted">
              Refund proposals below this limit with a matching operator task scope execute automatically.
            </p>
            <input
              aria-label="Auto-allow threshold in major currency units"
              type="range"
              min={10}
              max={200}
              step={5}
              value={autoAllow}
              onChange={(e) => setAutoAllow(Number(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-400">
              <span>10</span>
              <span>100</span>
              <span>200</span>
            </div>
          </div>

          {/* Hard Ceiling Threshold */}
          <div className="p-3.5 rounded bg-background border border-borderSubtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200">System Hard Ceiling</span>
              <span className="text-sm font-mono font-semibold text-red-400">{hardCeiling.toFixed(2)} units</span>
            </div>
            <p className="text-[11px] text-inkMuted">
              Absolute blast-radius ceiling. Any tool proposal exceeding this ceiling is unconditionally hard-blocked.
            </p>
            <input
              aria-label="Hard ceiling in major currency units"
              type="range"
              min={250}
              max={5000}
              step={50}
              value={hardCeiling}
              onChange={(e) => setHardCeiling(Number(e.target.value))}
              className="w-full accent-red-500 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-400">
              <span>250</span>
              <span>2,500</span>
              <span>5,000</span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 rounded bg-inkPrimary hover:bg-white text-slate-950 font-semibold text-xs flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isSaving ? 'Updating...' : 'Save Policy Rules'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
