import React from 'react';
import { motion } from 'motion/react';
import { ShieldCheck, RotateCcw, Activity, KeyRound, ClipboardCheck, ChartNoAxesColumn, Sliders, Wallet } from 'lucide-react';
import type { PolicyConfig } from '../types';
import { formatPolicyLimit } from '../policyMoney';

interface HeaderProps {
  policy: PolicyConfig | null;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingCount: number;
  onReset: () => void;
  isResetting: boolean;
  onChangeToken?: () => void;
  isAdmin: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  policy,
  activeTab,
  setActiveTab,
  pendingCount,
  onReset,
  isResetting,
  onChangeToken,
  isAdmin,
}) => {
  const tabs = [
    { id: 'approvals', label: 'Approvals', icon: ClipboardCheck, badge: pendingCount > 0 ? pendingCount : null },
    { id: 'eval', label: 'Test results', icon: ChartNoAxesColumn, badge: null },
    { id: 'policy', label: 'Refund rules', icon: Sliders, badge: null },
    { id: 'audit', label: 'Activity', icon: Activity, badge: null },
    { id: 'sandbox', label: 'Order balances', icon: Wallet, badge: null },
  ];

  const formatLimit = (amount: number) => formatPolicyLimit(amount) ?? '—';

  if (!isAdmin) return (
    <header className="sm:sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-3 py-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 shrink-0 rounded-xl bg-emerald-600 flex items-center justify-center text-white">
            <ShieldCheck className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <span className="block font-bold text-base text-slate-900 tracking-tight">AetherGuard</span>
            <p className="text-sm text-slate-500">Refund center</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {policy && formatPolicyLimit(policy.auto_allow_threshold) && (
            <span className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1.5 text-sm text-emerald-800">
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              Instant refunds up to <strong>{formatLimit(policy.auto_allow_threshold)}</strong>
            </span>
          )}
          <span className="text-sm font-semibold px-3 py-1.5 rounded-full bg-slate-100 text-slate-700" title="All amounts are Bangladeshi taka">
            BDT (৳)
          </span>
          {onChangeToken && (
            <button
              onClick={onChangeToken}
              className="min-h-[2.5rem] text-sm font-semibold px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition flex items-center gap-1.5 cursor-pointer"
            >
              <KeyRound className="w-4 h-4" aria-hidden="true" />
              <span>Sign out</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );

  return (
    <aside className="app-sidebar z-50 border-b border-borderSubtle lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:shrink-0 lg:flex-col lg:border-b-0 lg:border-r">
      <div className="flex items-center justify-between gap-3 px-4 py-3 lg:px-5 lg:py-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 shrink-0 rounded-lg bg-brand-500 flex items-center justify-center text-slate-950">
            <ShieldCheck className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <span className="block font-bold text-sm text-white tracking-tight">AetherGuard</span>
            <p className="text-xs text-slate-400">Admin console</p>
          </div>
        </div>
        <span className="text-xs font-semibold px-2 py-1 rounded-md bg-surfaceCard border border-borderStrong text-slate-300" title="All amounts are Bangladeshi taka">
          BDT (৳)
        </span>
      </div>

      <nav aria-label="Workspace sections" className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible lg:px-3 lg:pb-0">
        <p className="hidden lg:block px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Workspace</p>
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`relative flex min-h-[2.5rem] items-center gap-2.5 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition cursor-pointer ${
                isActive ? 'text-white' : 'text-slate-400 hover:bg-surfaceCard hover:text-slate-100'
              }`}
            >
              {isActive && (
                <motion.span
                  layoutId="nav-active"
                  aria-hidden="true"
                  className="absolute inset-0 rounded-md bg-surfaceCard border-l-2 border-brand-400"
                  transition={{ type: 'spring', bounce: 0, visualDuration: 0.3 }}
                />
              )}
              <tab.icon aria-hidden="true" className={`relative w-4 h-4 shrink-0 ${isActive ? 'text-brand-400' : ''}`} />
              <span className="relative">{tab.label}</span>
              {tab.badge !== null && (
                <span className="relative ml-auto rounded-full bg-amber-400 px-2 py-0.5 text-[11px] font-bold text-slate-950" aria-label={`${tab.badge} waiting`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="hidden lg:block mt-auto space-y-3 border-t border-borderSubtle p-4">
        {policy && (
          <dl className="space-y-1.5 rounded-lg border border-borderSubtle bg-surface p-3 text-xs">
            <div className="flex items-center gap-1.5 pb-1 font-semibold text-brand-400">
              <Activity className="w-3.5 h-3.5" aria-hidden="true" />Refund rules v{policy.version}
            </div>
            <div className="flex justify-between gap-2"><dt className="text-slate-400">Auto-approve up to</dt><dd className="font-mono text-emerald-400">{formatLimit(policy.auto_allow_threshold)}</dd></div>
            <div className="flex justify-between gap-2"><dt className="text-slate-400">Hard stop</dt><dd className="font-mono font-bold text-red-400">{formatLimit(policy.hard_ceiling_threshold)}</dd></div>
          </dl>
        )}
      </div>

      <div className="flex gap-2 border-t border-borderSubtle px-3 py-3 lg:px-4">
        <button
          onClick={onReset}
          disabled={isResetting}
          title="Reset synthetic orders and refund history"
          className="flex min-h-[2.5rem] flex-1 whitespace-nowrap items-center justify-center gap-1.5 rounded-md border border-borderStrong bg-surfaceCard px-3 py-2 text-sm font-medium text-slate-200 transition hover:bg-borderSubtle disabled:opacity-50 cursor-pointer"
        >
          <RotateCcw aria-hidden="true" className={`w-4 h-4 text-brand-400 ${isResetting ? 'animate-spin' : ''}`} />
          <span>{isResetting ? 'Resetting…' : 'Reset data'}</span>
        </button>
        {onChangeToken && (
          <button
            onClick={onChangeToken}
            title="Sign out"
            className="flex min-h-[2.5rem] items-center justify-center gap-1.5 rounded-md border border-borderSubtle px-3 py-2 text-sm text-slate-400 transition hover:bg-surfaceCard hover:text-slate-100 cursor-pointer"
          >
            <KeyRound className="w-4 h-4" aria-hidden="true" />
            <span>Sign out</span>
          </button>
        )}
      </div>
    </aside>
  );
};
