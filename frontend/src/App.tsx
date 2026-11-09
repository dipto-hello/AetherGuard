import { useState, useEffect } from 'react';
import type {
  Order,
  Refund,
  PolicyConfig,
  PendingAction,
  AuditEvent,
  BenchmarkTicket
} from './types';
import {
  fetchOrders,
  fetchRefunds,
  fetchPolicy,
  fetchPendingApprovals,
  fetchAuditLogs,
  fetchBenchmarkTickets,
  resetSandbox,
  setOperatorToken
} from './api';

import { Header } from './components/Header';
import { AgentArena } from './components/AgentArena';
import { ApprovalDesk } from './components/ApprovalDesk';
import { PolicyManager } from './components/PolicyManager';
import { AuditLedger } from './components/AuditLedger';
import { SandboxViewer } from './components/SandboxViewer';
import { EvaluationMatrix } from './components/EvaluationMatrix';
import { AlertCircle, RefreshCw } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('arena');
  const [orders, setOrders] = useState<Order[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [policy, setPolicy] = useState<PolicyConfig | null>(null);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [tickets, setTickets] = useState<BenchmarkTicket[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [unknownAttempt, setUnknownAttemptState] = useState<string | null>(() => {
    try { return sessionStorage.getItem('aetherguard_unknown_attempt'); } catch { return null; }
  });
  const setUnknownAttempt = (key: string | null) => {
    try {
      if (key) sessionStorage.setItem('aetherguard_unknown_attempt', key);
      else sessionStorage.removeItem('aetherguard_unknown_attempt');
    } catch { /* Storage may be unavailable; keep the warning in memory. */ }
    setUnknownAttemptState(key);
  };

  const loadAllData = async () => {
    try {
      const results = await Promise.allSettled([
        fetchOrders(),
        fetchRefunds(),
        fetchPolicy(),
        fetchPendingApprovals(),
        fetchAuditLogs(),
        fetchBenchmarkTickets(),
      ]);

      const [ordRes, refRes, polRes, pendingRes, logRes, ticketRes] = results;

      if (ordRes.status === 'fulfilled') setOrders(ordRes.value);
      if (refRes.status === 'fulfilled') setRefunds(refRes.value);
      if (polRes.status === 'fulfilled' && polRes.value) setPolicy(polRes.value);
      if (pendingRes.status === 'fulfilled') setPendingActions(pendingRes.value);
      if (logRes.status === 'fulfilled') setLogs(logRes.value);
      if (ticketRes.status === 'fulfilled') setTickets(ticketRes.value);

      const failures = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      if (failures.length > 0) {
        if (failures.some(f => f.reason?.message?.includes('Access denied'))) {
          setOperatorToken('');
          setAuthenticated(false);
          return;
        }
        if (failures.length === results.length) {
          setGlobalError(failures[0].reason instanceof Error ? failures[0].reason.message : 'Unable to load backend data.');
        }
      } else {
        setGlobalError(null);
      }
    } catch (err) {
      setGlobalError(err instanceof Error ? err.message : 'Unable to load backend data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    const fetchTelemetry = () => {
      if (active) loadAllData();
    };
    const timer = setTimeout(fetchTelemetry, 0);
    const interval = setInterval(fetchTelemetry, 5000);
    return () => {
      active = false;
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [authenticated]);

  const handleReset = async () => {
    if (!window.confirm('Reset synthetic orders and remove refund history?')) return;
    setIsResetting(true);
    try {
      await resetSandbox();
      await loadAllData();
    } catch {
      alert('Failed to reset sandbox');
    } finally {
      setIsResetting(false);
    }
  };

  if (!authenticated) {
    return (
      <main className="min-h-screen bg-background text-inkPrimary flex items-center justify-center p-6">
        <form className="w-full max-w-md bg-surface border border-borderSubtle rounded p-6 space-y-4" onSubmit={async (event) => {
          event.preventDefault();
          setIsConnecting(true);
          setConnectError(null);
          setOperatorToken(tokenInput);
          try {
            await fetchPolicy();
            setTokenInput('');
            setIsLoading(true);
            setAuthenticated(true);
          } catch (err) {
            setOperatorToken('');
            setConnectError(err instanceof Error ? err.message : 'Unable to connect.');
          } finally {
            setIsConnecting(false);
          }
        }}>
          <h1 className="text-lg font-semibold">AetherGuard operator access</h1>
          <p className="text-sm text-inkMuted">Enter the operator token configured on the server. It stays in this browser tab's memory.</p>
          <label htmlFor="operator-token" className="block text-sm">Operator token</label>
          <input id="operator-token" type="password" required autoComplete="off" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} className="w-full bg-background border border-borderStrong rounded px-3 py-2" />
          {connectError && <p role="alert" className="text-sm text-red-300">{connectError}</p>}
          <button className="px-4 py-2 rounded bg-inkPrimary text-slate-950 font-semibold disabled:opacity-50" type="submit" disabled={isConnecting}>{isConnecting ? 'Connecting…' : 'Connect'}</button>
        </form>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col font-sans selection:bg-brandCyan selection:text-slate-950">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-brandCyan focus:text-slate-950 focus:font-semibold focus:rounded focus:shadow-lg focus:outline-none"
      >
        Skip to main content
      </a>
      <Header
        policy={policy}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingCount={pendingActions.length}
        onReset={handleReset}
        isResetting={isResetting}
      />

      <main id="main-content" tabIndex={-1} className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 outline-none">
        <div className="flex justify-end mb-3"><button className="text-xs text-slate-300 underline" onClick={() => { setOperatorToken(''); setAuthenticated(false); }}>Change operator token</button></div>
        {globalError && (
          <div role="alert" className="mb-6 p-4 rounded-xl bg-brandRuby/10 border border-brandRuby/30 flex items-center justify-between text-xs text-brandRuby">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{globalError}</span>
            </div>
            <button
              onClick={loadAllData}
              className="px-2.5 py-1 rounded bg-brandRuby/20 hover:bg-brandRuby/30 text-white font-mono flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3 text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin text-brandCyan" />
            <span className="text-xs font-mono">Loading AetherGuard AgentOps telemetry...</span>
          </div>
        ) : (
          <>
            {activeTab === 'arena' && (
              <AgentArena tickets={tickets} onActionComplete={loadAllData} unknownAttempt={unknownAttempt} setUnknownAttempt={setUnknownAttempt} />
            )}

            {activeTab === 'approvals' && (
              <ApprovalDesk pendingActions={pendingActions} onActionDecided={loadAllData} />
            )}

            {activeTab === 'eval' && (
              <EvaluationMatrix />
            )}

            {activeTab === 'policy' && policy && (
              <PolicyManager policy={policy} onPolicyUpdated={(p) => setPolicy(p)} />
            )}

            {activeTab === 'audit' && (
              <AuditLedger logs={logs} />
            )}

            {activeTab === 'sandbox' && (
              <SandboxViewer orders={orders} refunds={refunds} onRefresh={loadAllData} />
            )}
          </>
        )}
      </main>

      <footer className="border-t border-borderSubtle bg-surface/50 py-4 text-center text-xs font-mono text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>AetherOps AI • International AI Builders Congress 2026</span>
          <span>Domain 11: InfraSphere AI • AgentOps Challenge</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
