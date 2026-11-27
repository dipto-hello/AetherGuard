import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  Order,
  Refund,
  PolicyConfig,
  PendingAction,
  AuditEvent
} from './types';
import {
  fetchOrders,
  fetchRefunds,
  fetchPolicy,
  fetchPendingApprovals,
  fetchAuditLogs,
  resetSandbox,
  setOperatorToken,
  fetchRole
} from './api';

import { Header } from './components/Header';
import { AgentArena } from './components/AgentArena';
import { ApprovalDesk } from './components/ApprovalDesk';
import { PolicyManager } from './components/PolicyManager';
import { AuditLedger } from './components/AuditLedger';
import { SandboxViewer } from './components/SandboxViewer';
import { EvaluationMatrix } from './components/EvaluationMatrix';
import { MyRequests } from './components/MyRequests';
import { loadMyRequests, saveMyRequests, type MyRequest } from './myRequests';
import { AlertCircle, RefreshCw, KeyRound, ShieldCheck } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('approvals');
  const [orders, setOrders] = useState<Order[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [policy, setPolicy] = useState<PolicyConfig | null>(null);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [logs, setLogs] = useState<AuditEvent[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [sandboxVersion, setSandboxVersion] = useState(0);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const [role, setRole] = useState<'admin' | 'user' | null>(null);
  const isAdmin = role === 'admin';
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [unknownAttempt, setUnknownAttemptState] = useState<string | null>(() => {
    try { return sessionStorage.getItem('aetherguard_unknown_attempt'); } catch { return null; }
  });
  const setUnknownAttempt = (key: string | null) => {
    try {
      if (key) sessionStorage.setItem('aetherguard_unknown_attempt', key);
      else sessionStorage.removeItem('aetherguard_unknown_attempt');
    } catch { /* Storage may be unavailable */ }
    setUnknownAttemptState(key);
  };

  const [myRequests, setMyRequestsState] = useState<MyRequest[]>(loadMyRequests);
  const setMyRequests = useCallback((update: (current: MyRequest[]) => MyRequest[]) => {
    setMyRequestsState((current) => {
      const next = update(current);
      saveMyRequests(next);
      return next;
    });
  }, []);

  const latestLoad = useRef(0);
  const polling = useRef(false);
  const invalidateDashboard = useCallback(() => {
    ++latestLoad.current;
    polling.current = false;
  }, []);

  const loadAllData = async () => {
    const load = ++latestLoad.current;
    polling.current = true;
    try {
      // Users may only call the refund-testing routes; admin-only data stays empty for them.
      const results = await Promise.allSettled([
        fetchOrders(),
        fetchPolicy(),
        isAdmin ? fetchRefunds() : Promise.resolve([] as Refund[]),
        isAdmin ? fetchPendingApprovals() : Promise.resolve([] as PendingAction[]),
        isAdmin ? fetchAuditLogs() : Promise.resolve([] as AuditEvent[]),
      ]);

      if (load !== latestLoad.current) return;
      const [ordRes, polRes, refRes, pendingRes, logRes] = results;

      if (ordRes.status === 'fulfilled') setOrders(ordRes.value);
      if (refRes.status === 'fulfilled') setRefunds(refRes.value);
      if (polRes.status === 'fulfilled' && polRes.value) setPolicy(polRes.value);
      if (pendingRes.status === 'fulfilled') setPendingActions(pendingRes.value);
      if (logRes.status === 'fulfilled') setLogs(logRes.value);

      const failures = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      if (failures.length > 0) {
        if (failures.some(f => f.reason?.message?.includes('Access denied'))) {
          setOperatorToken('');
          setRole(null);
          return;
        }
        setGlobalError(failures.length === results.length
          ? 'Unable to load dashboard data.'
          : 'Some dashboard data could not refresh. Displayed values may be stale.');
      } else {
        setGlobalError(null);
      }
    } catch (err) {
      if (load === latestLoad.current) setGlobalError(err instanceof Error ? err.message : 'Could not load dashboard data.');
    } finally {
      if (load === latestLoad.current) {
        polling.current = false;
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!role) return;
    let active = true;
    const fetchTelemetry = () => {
      if (active && !polling.current) loadAllData();
    };
    const timer = setTimeout(fetchTelemetry, 0);
    const interval = setInterval(fetchTelemetry, 5000);
    return () => {
      active = false;
      invalidateDashboard();
      clearTimeout(timer);
      clearInterval(interval);
    };
    // loadAllData only reads role, which is already a dependency.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [role, invalidateDashboard]);

  const handleReset = async () => {
    if (!window.confirm('Restore synthetic order balances, clear refund history, and expire pending approvals and scopes?')) return;
    setIsResetting(true);
    try {
      await resetSandbox();
      setSandboxVersion((version) => version + 1);
      await loadAllData();
    } catch {
      setGlobalError('Could not reset the data. Check the order balances before trying again.');
    } finally {
      setIsResetting(false);
    }
  };

  const handleDisconnect = () => {
    setOperatorToken('');
    setRole(null);
    setActiveTab('approvals');
  };

  // Login view when not authenticated
  if (!role) {
    return (
      <main className="theme-light min-h-screen flex items-center justify-center p-6">
        <form
          className="user-card w-full max-w-md p-8 space-y-5"
          onSubmit={async (event) => {
            event.preventDefault();
            setIsConnecting(true);
            setConnectError(null);
            setOperatorToken(tokenInput);
            try {
              const signedInRole = await fetchRole();
              setTokenInput('');
              setIsLoading(true);
              setRole(signedInRole);
            } catch (err) {
              setOperatorToken('');
              const message = err instanceof Error ? err.message : '';
              setConnectError(message.includes('Access denied')
                ? 'Incorrect password. Try again.'
                : 'Could not reach the server. Check that it is running.');
            } finally {
              setIsConnecting(false);
            }
          }}
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-emerald-600 flex items-center justify-center text-white">
              <ShieldCheck className="w-6 h-6" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">AetherGuard</h1>
              <p className="text-sm text-slate-500">Refund review</p>
            </div>
          </div>

          <div className="space-y-1.5 pt-2">
            <label htmlFor="operator-token" className="block text-sm font-semibold text-slate-800">
              Password
            </label>
            <p className="text-sm text-slate-500 leading-relaxed">
              Admin password: <span className="font-mono font-semibold text-slate-800">admin</span> · User password: <span className="font-mono font-semibold text-slate-800">user</span>
            </p>
            <input
              id="operator-token"
              type="password"
              required
              autoComplete="off"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              placeholder="Enter password"
              className="user-field font-mono"
            />
          </div>

          {connectError && (
            <p role="alert" className="text-sm text-red-800 bg-red-50 border border-red-200 p-3 rounded-lg">
              {connectError}
            </p>
          )}

          <button
            className="user-cta w-full"
            type="submit"
            disabled={isConnecting}
          >
            <KeyRound className="w-4 h-4" aria-hidden="true" />
            <span>{isConnecting ? 'Signing in…' : 'Sign in'}</span>
          </button>
        </form>
      </main>
    );
  }

  return (
    <div className={`min-h-screen flex flex-col font-sans ${isAdmin ? 'workspace-shell bg-background text-slate-100 selection:bg-brand-500 selection:text-slate-950' : 'theme-light'}`}>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-brand-500 focus:text-slate-950 focus:font-semibold focus:rounded-lg focus:shadow-lg focus:outline-none"
      >
        Skip to main content
      </a>

      {/* Main Top Header */}
      <Header
        policy={policy}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingCount={pendingActions.length}
        onReset={handleReset}
        isResetting={isResetting}
        onChangeToken={handleDisconnect}
        isAdmin={isAdmin}
      />

      <main id="main-content" tabIndex={-1} className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 outline-none">
        {globalError && (
          <div role="alert" className={`mb-6 p-4 rounded-xl border flex items-center justify-between ${isAdmin ? 'bg-red-950/30 border-red-800/40 text-xs text-red-300' : 'bg-red-50 border-red-200 text-sm text-red-800'}`}>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" aria-hidden="true" />
              <span>{globalError}</span>
            </div>
            <button
              onClick={loadAllData}
              className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${isAdmin ? 'bg-red-900/40 hover:bg-red-800/60 text-white font-mono' : 'bg-white border border-red-300 hover:bg-red-100 text-red-800 font-semibold'}`}
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {isLoading ? (
          <div role="status" className="flex flex-col items-center justify-center py-24 gap-3 text-slate-500">
            <RefreshCw className={`w-7 h-7 animate-spin ${isAdmin ? 'text-brand-400' : 'text-emerald-600'}`} aria-hidden="true" />
            <span className="text-sm">Loading…</span>
          </div>
        ) : (
          <>
            {!isAdmin && (
              <AgentArena
                key={sandboxVersion}
                onActionComplete={loadAllData}
                unknownAttempt={unknownAttempt}
                setUnknownAttempt={setUnknownAttempt}
                orders={orders}
                policy={policy}
                onRequestRecorded={(request) => setMyRequests((current) => [request, ...current])}
              />
            )}
            {!isAdmin && <MyRequests requests={myRequests} setRequests={setMyRequests} />}

            {isAdmin && activeTab === 'approvals' && (
              <ApprovalDesk
                pendingActions={pendingActions}
                onActionDecided={loadAllData}
                onNavigateTab={(tab) => setActiveTab(tab)}
              />
            )}

            {isAdmin && activeTab === 'eval' && (
              <EvaluationMatrix />
            )}

            {isAdmin && activeTab === 'policy' && policy && (
              <PolicyManager
                policy={policy}
                onPolicyUpdated={(p) => { setPolicy(p); void loadAllData(); }}
              />
            )}

            {isAdmin && activeTab === 'audit' && (
              <AuditLedger logs={logs} />
            )}

            {isAdmin && activeTab === 'sandbox' && (
              <SandboxViewer
                orders={orders}
                refunds={refunds}
                onRefresh={() => { void loadAllData(); }}
                onOrderUpdated={(updated) => {
                  setOrders((current) => current.map((order) => order.id === updated.id ? updated : order));
                  void loadAllData();
                }}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
