import type {
  Order,
  Refund,
  TaskScope,
  PendingAction,
  AuditEvent,
  PolicyConfig,
  BenchmarkTicket,
  AgentTrace,
  EvaluationReport
} from './types';

const BASE_URL = '';
let operatorToken = '';

export function setOperatorToken(token: string) {
  operatorToken = token;
}

async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (typeof data?.detail?.message === 'string') return data.detail.message;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((err: any) => err.msg || JSON.stringify(err)).join(', ');
    }
    if (typeof data?.message === 'string') return data.message;
    if (typeof data?.error === 'string') return data.error;
  } catch {
    // Non-JSON response body
  }
  return res.statusText || fallback;
}

async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (operatorToken) headers.set('Authorization', `Bearer ${operatorToken}`);
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 || response.status === 403) throw new Error('Access denied. Check the operator token.');
  if (response.status === 503) {
    let errorDetail = '';
    try {
      const errorBody = await response.clone().json();
      errorDetail = typeof errorBody?.detail === 'string' ? errorBody.detail : '';
    } catch {
      // empty body or not JSON
    }
    if (!errorDetail || errorDetail.includes('operator') || errorDetail.includes('configured')) {
      throw new Error('The server is not configured for operator access.');
    }
    throw new Error(errorDetail);
  }
  return response;
}

export async function fetchExchangeRate(signal: AbortSignal): Promise<{
  bdt_per_usd: number; as_of: string; source: 'exchange_rate_api' | 'bangladesh_bank'; stale: boolean;
}> {
  const response = await apiFetch('/api/sandbox/exchange-rate', { signal });
  if (!response.ok) throw new Error('Could not load the exchange rate.');
  return response.json();
}

export async function fetchOrders(): Promise<Order[]> {
  const res = await apiFetch(`${BASE_URL}/api/sandbox/orders`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch sandbox orders'));
  const data = await res.json();
  return data.orders;
}

export async function updateOrderPaidAmount(order: Order, paidAmount: number): Promise<Order> {
  const res = await apiFetch(`/api/sandbox/orders/${encodeURIComponent(order.id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      paid_amount: paidAmount,
      expected_paid_amount: order.paid_amount,
      expected_refundable_amount: order.refundable_amount,
    }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Could not update the order.'));
  return (await res.json()).order;
}

export async function fetchRefunds(): Promise<Refund[]> {
  const res = await apiFetch(`${BASE_URL}/api/sandbox/refunds`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch refunds'));
  const data = await res.json();
  return data.refunds;
}

export async function resetSandbox(): Promise<string> {
  const res = await apiFetch(`${BASE_URL}/api/sandbox/reset`, { method: 'POST' });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to reset sandbox'));
  const data = await res.json();
  return data.message;
}

export async function fetchPolicy(): Promise<PolicyConfig> {
  const res = await apiFetch(`${BASE_URL}/api/governance/policy`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch policy configuration'));
  const data = await res.json();
  return data.policy;
}

export async function updatePolicy(updates: Partial<PolicyConfig>): Promise<PolicyConfig> {
  const res = await apiFetch(`${BASE_URL}/api/governance/policy`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to update policy'));
  const data = await res.json();
  return data.policy;
}

export async function createTaskScope(scope: {
  order_id: string;
  allowed_action: string;
  max_amount: number;
  allowed_currency: string;
  allowed_destination: string;
  expires_in_hours: number;
}): Promise<TaskScope> {
  const res = await apiFetch(`${BASE_URL}/api/governance/scopes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scope)
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to create task scope'));
  const data = await res.json();
  return data.scope;
}

export async function fetchPendingApprovals(): Promise<PendingAction[]> {
  const res = await apiFetch(`${BASE_URL}/api/governance/pending-approvals`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch pending approvals'));
  const data = await res.json();
  return data.pending_actions;
}

export async function decideApproval(
  actionId: string,
  decision: 'approve' | 'reject',
  reviewerId: string,
  reason?: string
): Promise<{ status: string; refund?: Refund }> {
  const res = await apiFetch(`${BASE_URL}/api/governance/approvals/${actionId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, reviewer_id: reviewerId, reason })
  });
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res, 'Failed to submit approval decision'));
  }
  const data = await res.json();
  return data.result;
}

export async function fetchAuditLogs(): Promise<AuditEvent[]> {
  const res = await apiFetch(`${BASE_URL}/api/governance/audit-logs?limit=50`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch audit logs'));
  const data = await res.json();
  return data.logs;
}

export async function fetchBenchmarkTickets(): Promise<BenchmarkTicket[]> {
  const res = await apiFetch(`${BASE_URL}/api/agent/tickets`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to fetch tickets'));
  const data = await res.json();
  return data.tickets;
}

export async function processAgentTicket(
  ticketText: string,
  scopeId?: string,
  idempotencyKey?: string,
  expectedAmount?: number,
): Promise<AgentTrace> {
  const res = await apiFetch(`${BASE_URL}/api/agent/process-ticket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticket_text: ticketText,
      scope_id: scopeId,
      expected_amount: expectedAmount,
      idempotency_key: idempotencyKey
    })
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to process ticket with agent'));
  const data = await res.json();
  return data.trace;
}

export async function runEvaluationSuite(): Promise<EvaluationReport> {
  const res = await apiFetch(`${BASE_URL}/api/evaluation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Failed to run evaluation suite'));
  const data = await res.json();
  return data.report;
}

export async function lookupAction(key: string): Promise<{ action_id: string; status: string; refund: Refund | null }> {
  const params = new URLSearchParams({ idempotency_key: key });
  const res = await apiFetch(`${BASE_URL}/api/governance/actions/lookup?${params}`);
  if (res.status === 404) throw new Error('No action is recorded yet. A request may still be in progress; do not assume it is safe to retry.');
  if (!res.ok) throw new Error(await extractErrorMessage(res, 'Could not check the action outcome.'));
  return (await res.json()).action;
}
