export interface MyRequest {
  key: string;
  orderId: string;
  amount: number;
  status: string;
}

// shortcut: kept in this browser only, since all users share one token; move to the backend if users get their own accounts.
const STORAGE_KEY = 'aetherguard_my_requests';

export function loadMyRequests(): MyRequest[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]'); } catch { return []; }
}

export function saveMyRequests(requests: MyRequest[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(requests)); } catch { /* Storage may be unavailable */ }
}

export const isOpen = (status: string) => status === 'pending' || status === 'executing';

export const statusLabel = (status: string) =>
  isOpen(status) ? 'Pending' : status === 'executed' ? 'Accepted' : status === 'rejected' ? 'Rejected' : 'Closed';
