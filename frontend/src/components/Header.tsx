import React from 'react';
import { ShieldCheck, RotateCcw, Activity } from 'lucide-react';
import type { PolicyConfig } from '../types';

interface HeaderProps {
  policy: PolicyConfig | null;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingCount: number;
  onReset: () => void;
  isResetting: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  policy,
  activeTab,
  setActiveTab,
  pendingCount,
  onReset,
  isResetting
}) => {
  const tabs = [
    { id: 'arena', label: 'Agent Arena', badge: null },
    { id: 'approvals', label: 'Approval Desk', badge: pendingCount > 0 ? pendingCount : null },
    { id: 'eval', label: 'Evaluation Matrix', badge: '10 Cases' },
    { id: 'policy', label: 'Policy Engine', badge: null },
    { id: 'audit', label: 'Audit Ledger', badge: null },
    { id: 'sandbox', label: 'Sandbox DB', badge: null },
  ];

  return (
    <header className="app-header border-b border-borderSubtle bg-surface sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo & Platform Info */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded border border-borderStrong bg-surfaceCard flex items-center justify-center text-brandAccent">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm tracking-wide text-inkPrimary">AetherGuard</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surfaceCard text-slate-400 border border-borderSubtle">
                  Synthetic demo
                </span>
              </div>
              <p className="text-[11px] text-inkMuted font-mono">
                Agent action governance
              </p>
            </div>
          </div>

          {/* Telemetry Badge & Quick Sandbox Reset */}
          <div className="flex items-center gap-3">
            {policy && (
              <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded bg-surfaceCard border border-borderSubtle text-[11px] font-mono text-inkMuted">
                <div className="flex items-center gap-1.5 text-brandEmerald">
                  <Activity className="w-3 h-3" />
                  <span>Rule v{policy.version}</span>
                </div>
                <span className="text-slate-600">|</span>
                <span>Auto: &le;{(policy.auto_allow_threshold / 100).toFixed(2)} units</span>
                <span className="text-slate-600">|</span>
                <span>Ceiling: {(policy.hard_ceiling_threshold / 100).toFixed(2)} units</span>
              </div>
            )}

            <button
              onClick={onReset}
              disabled={isResetting}
              title="Reset synthetic orders and refund history"
              aria-label="Reset synthetic sandbox"
              className="text-xs px-2.5 py-1 rounded bg-surfaceCard hover:bg-slate-800 text-slate-300 border border-borderSubtle flex items-center gap-1.5 font-mono transition disabled:opacity-50"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{isResetting ? 'Resetting...' : 'Reset Sandbox'}</span>
            </button>
          </div>
        </div>

        {/* Navigation Tabs - Underline / Crisp Pill Pattern */}
        <nav aria-label="Workspace sections" className="workspace-nav flex space-x-1 border-t border-borderSubtle pt-1 pb-1.5 -mb-px overflow-x-auto scrollbar-none">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded transition whitespace-nowrap ${
                  isActive
                    ? 'bg-surfaceCard text-white border border-borderStrong'
                    : 'text-inkMuted hover:text-slate-200 hover:bg-surfaceCard/50'
                }`}
              >
                <span>{tab.label}</span>
                {tab.badge !== null && (
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                      isActive
                        ? 'bg-brandAccent/20 text-brandAccent'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
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
