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
    try {
      const res = await runEvaluationSuite();
      setReport(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to execute evaluation suite');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Banner & Trigger */}
      <div className="bg-surface rounded border border-borderSubtle p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <Award className="w-4 h-4 text-inkMuted" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-inkPrimary">
                10-Case Adversarial &amp; Legitimate Benchmark Suite
              </h2>
            </div>
            <p className="text-xs text-inkMuted">
              Deterministic boundary cases using synthetic actions. This suite does not test a live model or prompt injection.
            </p>
          </div>

          <button
            onClick={handleRunEvaluation}
            disabled={isRunning}
            className="px-4 py-2 rounded bg-inkPrimary hover:bg-white text-slate-950 font-semibold text-xs flex items-center gap-2 transition disabled:opacity-50 shrink-0"
          >
            {isRunning ? (
              <>
                <Zap className="w-3.5 h-3.5 animate-spin" />
                <span>Running boundary cases...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run boundary cases</span>
              </>
            )}
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 mt-3 rounded bg-red-950/20 border border-red-800/40 text-xs text-red-300 flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* Metrics Row - Quiet Type Over Tiles */}
      {report && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded bg-surface border border-borderSubtle">
            <span className="text-[11px] font-mono text-inkMuted block mb-0.5">Policy Decision Accuracy</span>
            <div className="text-2xl font-mono font-semibold text-emerald-400">
              {report.accuracy_percent}%
            </div>
            <div className="text-[10px] text-slate-500 font-mono mt-1">
              {report.passed_cases}/{report.total_cases} cases passed
            </div>
          </div>

          <div className="p-3.5 rounded bg-surface border border-borderSubtle">
            <span className="text-[11px] font-mono text-inkMuted block mb-0.5">Unauthorized Backend Writes</span>
            <div className="text-2xl font-mono font-semibold text-emerald-400">
              {report.unauthorized_backend_writes ?? 'N/A'}
            </div>
            <div className="text-[10px] text-slate-500 font-mono mt-1">
              Cases with unexpected observed changes
            </div>
          </div>

          <div className="p-3.5 rounded bg-surface border border-borderSubtle">
            <span className="text-[11px] font-mono text-inkMuted block mb-0.5">False Positive Rate</span>
            <div className="text-2xl font-mono font-semibold text-white">
              {report.false_positive_rate == null ? 'N/A' : `${report.false_positive_rate}%`}
            </div>
            <div className="text-[10px] text-slate-500 font-mono mt-1">
              Among classified legitimate cases
            </div>
          </div>

          <div className="p-3.5 rounded bg-surface border border-borderSubtle">
            <span className="text-[11px] font-mono text-inkMuted block mb-0.5">Adversarial cases not hard-blocked</span>
            <div className="text-2xl font-mono font-semibold text-white">
              {report.false_negative_rate == null ? 'N/A' : `${report.false_negative_rate}%`}
            </div>
            <div className="text-[10px] text-slate-500 font-mono mt-1">
              Includes decisions held for approval
            </div>
          </div>
        </div>
      )}

      {/* Benchmark Cases Table - Quiet Lines, Sentence Case, Right-aligned Numbers */}
      {report && (
        <div className="bg-surface rounded border border-borderSubtle p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-inkPrimary">
              Benchmark Trajectory Execution Breakdown
            </h3>
            <span className="text-[10px] font-mono text-inkMuted">
              Execution timestamp: {report.timestamp}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-borderSubtle text-[11px] text-inkMuted">
                  <th className="py-2 px-2.5 font-normal">Case</th>
                  <th className="py-2 px-2.5 font-normal">Scenario Name &amp; Invariant</th>
                  <th className="py-2 px-2.5 font-normal">Category</th>
                  <th className="py-2 px-2.5 font-normal">Expected</th>
                  <th className="py-2 px-2.5 font-normal">Actual Decision</th>
                  <th className="py-2 px-2.5 font-normal">Expected / actual effect</th>
                  <th className="py-2 px-2.5 font-normal text-right">Latency</th>
                  <th className="py-2 px-2.5 font-normal text-right">Verification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-borderSubtle">
                {report.cases.map((c) => {
                  const isPassed = c.status === 'PASSED';
                  return (
                    <tr key={c.case_id} className="hover:bg-surfaceCard/50 transition">
                      <td className="py-2.5 px-2.5 font-semibold text-white whitespace-nowrap">
                        {c.case_id}
                      </td>
                      <td className="py-2.5 px-2.5">
                        <div className="font-medium text-slate-200">{c.name}</div>
                        <div className="text-[10px] text-inkMuted line-clamp-1">{c.description}</div>
                      </td>
                      <td className="py-2.5 px-2.5 text-inkMuted">
                        {c.category}
                      </td>
                      <td className="py-2.5 px-2.5 text-slate-400">
                        {c.expected_verdict}
                      </td>
                      <td className="py-2.5 px-2.5">
                        <span
                          className={`px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                            c.actual_verdict === 'ALLOWED'
                              ? 'bg-emerald-500/10 text-emerald-400'
                              : c.actual_verdict === 'APPROVAL_REQUIRED'
                              ? 'bg-amber-500/10 text-amber-400'
                              : 'bg-red-500/10 text-red-400'
                          }`}
                        >
                          {c.actual_verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-2.5 text-inkMuted">{c.expected_backend_effect} / {c.actual_backend_effect}</td>
                      <td className="py-2.5 px-2.5 text-right tabular-nums text-inkMuted">
                        {c.latency_ms.toFixed(1)}ms
                      </td>
                      <td className="py-2.5 px-2.5 text-right">
                        <span
                          className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                            isPassed
                              ? 'text-emerald-400 bg-emerald-500/10'
                              : 'text-red-400 bg-red-500/10'
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
