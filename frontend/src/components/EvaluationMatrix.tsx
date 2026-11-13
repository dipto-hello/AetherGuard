import React, { useState } from 'react';
import type { EvaluationReport } from '../types';
import { runEvaluationSuite } from '../api';
import { Play, AlertTriangle, Award, Zap } from 'lucide-react';

export const EvaluationMatrix: React.FC = () => {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRunEvaluation = async () => {
    setIsRunning(true);
    setErrorMsg(null);
    setReport(null);
    try {
      const res = await runEvaluationSuite();
      setReport(res);
    } catch {
      setErrorMsg('Could not finish the tests. Try again.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Trigger */}
      <div className="bg-surface rounded-xl border border-borderSubtle p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Award className="w-5 h-5 text-brand-400" />
              <h1 className="text-base font-bold text-white">
                Refund rule tests
              </h1>
            </div>
            <p className="text-sm text-slate-400">
              Runs USD and BDT test cases with the default refund rules. Your demo orders stay as they are.
            </p>
          </div>

          <button
            onClick={handleRunEvaluation}
            disabled={isRunning}
            className="px-5 py-2.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition disabled:opacity-50 shrink-0 shadow-sm"
          >
            {isRunning ? (
              <>
                <Zap className="w-4 h-4 animate-spin text-slate-950" />
                <span>Running tests…</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Run tests</span>
              </>
            )}
          </button>
        </div>

        {errorMsg && (
          <div role="alert" aria-live="assertive" className="p-3 mt-4 rounded-lg bg-red-950/40 border border-red-800/60 text-xs text-red-300 flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {report && (
        <dl className="grid grid-cols-2 lg:grid-cols-4 gap-4" aria-live="polite">
          {[
            ['Cases passed', `${report.passed_cases} / ${report.total_cases}`],
            ['Unexpected balance changes', report.unauthorized_backend_writes ?? 'Not measured'],
            ['Valid requests blocked', report.false_positive_rate == null ? 'Not measured' : `${report.false_positive_rate}%`],
            ['Unsafe cases with the wrong decision', report.false_negative_rate == null ? 'Not measured' : `${report.false_negative_rate}%`],
          ].map(([label, value]) => (
            <div key={label} className="p-4 rounded-xl bg-surface border border-borderSubtle space-y-1">
              <dt className="text-xs text-slate-400">{label}</dt>
              <dd className="text-lg font-mono font-bold text-white">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* Benchmark Cases Table */}
      {report && (
        <div className="bg-surface rounded-xl border border-borderSubtle p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white">
              Results by test
            </h3>
            <span className="text-xs font-mono text-slate-400">
              Timestamp: {report.timestamp}
            </span>
          </div>

          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Refund test details">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-borderSubtle text-[11px] text-slate-400">
                  <th className="py-2.5 px-3 font-semibold">Case</th>
                  <th className="py-2.5 px-3 font-semibold">Example request</th>
                  <th className="py-2.5 px-3 font-semibold">Category</th>
                  <th className="py-2.5 px-3 font-semibold">Expected</th>
                  <th className="py-2.5 px-3 font-semibold">Decision</th>
                  <th className="py-2.5 px-3 font-semibold">Order balance change</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Case time</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-borderSubtle">
                {report.cases.map((c) => {
                  const isPassed = c.status === 'PASSED';
                  return (
                    <tr key={c.case_id} className="hover:bg-surfaceCard/60 transition">
                      <td className="py-2.5 px-3 font-bold text-white whitespace-nowrap">
                        {c.case_id}
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-slate-200">{c.name}</div>
                        <div className="text-[11px] text-slate-400">{c.description}</div>
                        <div className="text-[11px] text-slate-400">{c.reason}</div>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {c.category}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {c.expected_verdict}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.actual_verdict === 'ALLOWED'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              : c.actual_verdict === 'APPROVAL_REQUIRED'
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : 'bg-red-500/20 text-red-400 border border-red-500/30'
                          }`}
                        >
                          {c.actual_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <div>{c.actual_backend_effect}</div>
                        <div className="text-slate-400">Expected {c.expected_backend_effect}</div>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-slate-400">
                        {c.latency_ms.toFixed(1)}ms
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isPassed
                              ? 'text-emerald-400 bg-emerald-500/20 border border-emerald-500/40'
                              : 'text-red-400 bg-red-500/20 border border-red-500/40'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
