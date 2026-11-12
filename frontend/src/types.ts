export interface Order {
  id: string;
  customer_name: string;
  currency: string;
  paid_amount: number;
  refundable_amount: number;
  original_destination: string;
  status: 'paid' | 'partially_refunded' | 'fully_refunded';
  created_at: string;
}

export interface Refund {
  id: string;
  order_id: string;
  amount: number;
  currency: string;
  destination: string;
  idempotency_key: string;
  action_id: string;
  status: string;
  created_at: string;
}

export interface TaskScope {
  scope_id: string;
  operator_id: string;
  order_id: string;
  allowed_action: string;
  max_amount: number;
  allowed_currency: string;
  allowed_destination: string;
  expires_at: string;
  created_at?: string;
}

export interface PendingAction {
  action_id: string;
  tool: string;
  arguments: {
    order_id?: string;
    amount?: number;
    currency?: string;
    destination?: string;
    reason?: string;
    [key: string]: any;
  };
  fingerprint: string;
  task_scope_id?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'executing' | 'executed';
  reason: string;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  action_id: string;
  tool: string;
  verdict: 'ALLOWED' | 'APPROVAL_REQUIRED' | 'BLOCKED' | 'APPROVED' | 'REJECTED' | 'ORDER_BALANCE_UPDATED' | 'POLICY_UPDATED' | 'SANDBOX_RESET';
  reason: string;
  fingerprint: string;
  details: string;
  created_at: string;
}

export interface PolicyConfig {
  version: string;
  allowed_tools: string[];
  auto_allow_threshold: number;
  hard_ceiling_threshold: number;
  enforce_task_scope: boolean;
  require_exact_destination_match: boolean;
}

export interface BenchmarkTicket {
  id: string;
  title: string;
  language: 'en' | 'bn';
  category: string;
  text: string;
  expected_order_id: string;
  expected_amount: number;
  expected_currency: string;
  expected_destination: string;
  description: string;
}

export interface PipelineStage {
  id: string;
  name: string;
  status: string;
  details: string;
}

export interface AgentTrace {
  ticket_text: string;
  language: string;
  agent_mode: string;
  parsed_parameters: {
    order_id: string;
    currency: string;
    amount: number;
    destination: string;
    language: string;
  };
  order_state?: {
    order_id: string;
    paid_amount: number;
    refundable_amount: number;
    original_destination: string;
  };
  proposed_tool: string;
  boundary_verdict: 'ALLOWED' | 'APPROVAL_REQUIRED' | 'BLOCKED';
  boundary_reason: string;
  executed: boolean;
  action_id?: string;
  fingerprint?: string;
  refund?: Refund;
  pending_approval: boolean;
  transport: string;
  pipeline_stages?: PipelineStage[];
}

export interface EvaluationCase {
  case_id: string;
  name: string;
  category: string;
  description: string;
  expected_verdict: string;
  actual_verdict: string;
  expected_backend_effect: string;
  actual_backend_effect: string;
  status: 'PASSED' | 'FAILED';
  reason: string;
  latency_ms: number;
}

export interface EvaluationReport {
  timestamp: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  accuracy_percent: number;
  unauthorized_backend_writes: number | null;
  false_positive_rate: number | null;
  false_negative_rate: number | null;
  cases: EvaluationCase[];
}
