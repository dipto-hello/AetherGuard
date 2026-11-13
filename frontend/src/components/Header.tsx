import React from 'react';
import { ShieldCheck, RotateCcw, Activity, KeyRound, FlaskConical, ClipboardCheck, ChartNoAxesColumn, Sliders, Wallet } from 'lucide-react';
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
  currencyMode: 'USD' | 'BDT';
  bdtPerUsd?: number;
  setCurrencyMode: (mode: 'USD' | 'BDT') => void;
}

export const Header: React.FC<HeaderProps> = ({
  policy,
  activeTab,
  setActiveTab,
  pendingCount,
  onReset,
  isResetting,
  onChangeToken,
  currencyMode,
  bdtPerUsd,
  setCurrencyMode
}) => {
  const tabs = [
    { id: 'arena', label: 'Test a refund', icon: FlaskConical, badge: null },
    { id: 'approvals', label: 'Approvals', icon: ClipboardCheck, badge: pendingCount > 0 ? pendingCount : null },
    { id: 'eval', label: 'Test results', icon: ChartNoAxesColumn, badge: null },
    { id: 'policy', label: 'Refund rules', icon: Sliders, badge: null },
    { id: 'audit', label: 'Activity', icon: Activity, badge: null },
    { id: 'sandbox', label: 'Order balances', icon: Wallet, badge: null },
  ];

  const formatLimit = (amount: number) => formatPolicyLimit(amount, currencyMode, bdtPerUsd) ?? '—';

  return (
    <header className="app-header border-b border-borderSubtle sm:sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top Branding & Status Row */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
          {/* Logo & Identity */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 shrink-0 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base text-white tracking-tight">AetherGuard</span>
              </div>
              <p className="text-xs text-slate-400">
                Refund demo
              </p>
            </div>
          </div>

          {/* Policy Badges & Controls */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {policy && (
              <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-surfaceCard border border-borderSubtle text-xs font-mono text-slate-300">
                <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                  <Activity className="w-3.5 h-3.5" />
                  <span>Rule v{policy.version}</span>
                </div>
                <span className="text-slate-600">|</span>
                <span>Refunds above the auto-approve limit require approval</span>
                <span className="text-slate-600">|</span>
                <span>
                  Hard Stop:{' '}
                  <strong className="text-red-400 font-bold">
                    {formatLimit(policy.hard_ceiling_threshold)}
                  </strong>
                </span>
              </div>
            )}

            {/* Currency Mode Switcher Pill */}
            <div className="flex items-center bg-surfaceCard border border-borderStrong rounded-lg p-0.5" role="group" aria-label="Demo currency">
              <button
                type="button"
                aria-pressed={currencyMode === 'USD'}
                onClick={() => setCurrencyMode('USD')}
                className={`px-2.5 py-1 rounded-md text-xs font-bold transition flex items-center gap-1 ${
                  currencyMode === 'USD'
                    ? 'bg-emerald-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Show USD demo scenarios"
              >
                <span>USD ($)</span>
              </button>
              <button
                type="button"
                aria-pressed={currencyMode === 'BDT'}
                onClick={() => setCurrencyMode('BDT')}
                className={`px-2.5 py-1 rounded-md text-xs font-bold transition flex items-center gap-1 ${
                  currencyMode === 'BDT'
                    ? 'bg-cyan-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Show BDT demo scenarios"
              >
                <span>BDT (৳)</span>
              </button>
            </div>

            <button
              onClick={onReset}
              disabled={isResetting}
              title="Reset synthetic orders and refund history"
              aria-label="Reset demo data"
              className="text-xs px-3 py-1.5 rounded-lg bg-surfaceCard hover:bg-slate-800 text-slate-200 border border-borderStrong flex items-center gap-1.5 font-medium transition disabled:opacity-50"
            >
              <RotateCcw className={`w-3.5 h-3.5 text-brandCyan ${isResetting ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{isResetting ? 'Resetting...' : 'Reset Demo Data'}</span>
            </button>

            {onChangeToken && (
              <button
                onClick={onChangeToken}
                title="Sign out"
                aria-label="Sign out"
                className="text-xs px-2.5 py-1.5 rounded-lg bg-surfaceCard hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-borderSubtle transition flex items-center gap-1"
              >
                <KeyRound className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Sign out</span>
              </button>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav aria-label="Workspace sections" className="workspace-nav flex flex-wrap border-t border-borderSubtle/60">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition whitespace-nowrap ${
                  isActive
                    ? 'bg-emerald-400/10 text-emerald-200 border border-emerald-400/25'
                    : 'border border-transparent text-slate-400 hover:text-white hover:bg-surfaceCard'
                }`}
              >
                <tab.icon aria-hidden="true" className="w-4 h-4 shrink-0" />
                <span>{tab.label}</span>
                {tab.badge !== null && (
                  <span className="rounded-full bg-amber-400 px-2 py-0.5 text-[10px] font-bold text-slate-950">
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
