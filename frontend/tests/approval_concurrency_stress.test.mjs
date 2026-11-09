import assert from 'node:assert/strict';
import test from 'node:test';
import * as api from '../src/api.ts';

// Test harness simulating ApprovalDesk component state and logic directly
function createApprovalDeskHarness(onActionDecided = async () => {}) {
  let processingId = null;
  let errorMsg = null;
  let successMsg = null;
  const inFlightRef = { current: new Set() };
  let apiCallLog = [];

  const handleDecision = async (actionId, decision) => {
    if (inFlightRef.current.has(actionId)) return;
    inFlightRef.current.add(actionId);
    processingId = actionId;
    errorMsg = null;
    successMsg = null;

    try {
      apiCallLog.push({ actionId, decision, timestamp: Date.now() });
      const res = await api.decideApproval(actionId, decision, 'demo_operator');
      successMsg = `Action #${actionId} successfully processed: status ${res.status}.`;
      await onActionDecided();
      return res;
    } catch (err) {
      errorMsg = err.message || 'Failed to process approval decision';
      throw err;
    } finally {
      inFlightRef.current.delete(actionId);
      processingId = null;
    }
  };

  return {
    handleDecision,
    getState: () => ({ processingId, errorMsg, successMsg, inFlightSize: inFlightRef.current.size }),
    getApiCallLog: () => apiCallLog,
  };
}

test('ApprovalDesk: rapid synchronous 10x multi-click executes API exactly once', async () => {
  let serverHits = 0;
  globalThis.fetch = async () => {
    serverHits++;
    // Simulate 20ms network latency
    await new Promise((r) => setTimeout(r, 20));
    return new Response(JSON.stringify({ result: { status: 'executed' } }), { status: 200 });
  };

  const desk = createApprovalDeskHarness();

  // Burst 10 rapid synchronous clicks on the same action
  const promises = [];
  for (let i = 0; i < 10; i++) {
    promises.push(desk.handleDecision('act-rapid-1', 'approve'));
  }

  await Promise.all(promises);

  assert.equal(serverHits, 1, 'decideApproval must be invoked exactly once');
  assert.equal(desk.getApiCallLog().length, 1);
  assert.equal(desk.getState().processingId, null, 'processingId must be reset after completion');
  assert.equal(desk.getState().inFlightSize, 0, 'inFlight set must be empty');
  assert.match(desk.getState().successMsg, /Action #act-rapid-1 successfully processed/);
});

test('ApprovalDesk: conflicting approve + reject synchronous clicks drops the second action', async () => {
  let serverHits = 0;
  globalThis.fetch = async () => {
    serverHits++;
    await new Promise((r) => setTimeout(r, 15));
    return new Response(JSON.stringify({ result: { status: 'executed' } }), { status: 200 });
  };

  const desk = createApprovalDeskHarness();

  // Synchronously click 'approve' then immediately 'reject'
  const pApprove = desk.handleDecision('act-conflict-1', 'approve');
  const pReject = desk.handleDecision('act-conflict-1', 'reject');

  await Promise.all([pApprove, pReject]);

  assert.equal(serverHits, 1, 'Only one decision must reach the server');
  assert.equal(desk.getApiCallLog()[0].decision, 'approve', 'First decision must win');
  assert.equal(desk.getApiCallLog().length, 1, 'Reject decision must be dropped');
});

test('ApprovalDesk: error in decideApproval releases in-flight lock for operator retry', async () => {
  let callCount = 0;
  globalThis.fetch = async () => {
    callCount++;
    if (callCount === 1) {
      return new Response(JSON.stringify({ detail: 'Transient 500 error' }), { status: 500 });
    }
    return new Response(JSON.stringify({ result: { status: 'executed' } }), { status: 200 });
  };

  const desk = createApprovalDeskHarness();

  // 1st attempt fails
  await assert.rejects(
    desk.handleDecision('act-retry-1', 'approve'),
    /Transient 500 error/
  );

  assert.equal(desk.getState().inFlightSize, 0, 'Lock must be released on failure');
  assert.equal(desk.getState().processingId, null);
  assert.match(desk.getState().errorMsg, /Transient 500 error/);

  // 2nd attempt (operator retries) succeeds
  await desk.handleDecision('act-retry-1', 'approve');
  assert.equal(callCount, 2);
  assert.equal(desk.getState().errorMsg, null);
  assert.match(desk.getState().successMsg, /Action #act-retry-1 successfully processed/);
});

test('ApprovalDesk: lock held through onActionDecided refresh cycle', async () => {
  let refreshStarted = false;
  let refreshFinished = false;

  globalThis.fetch = async () => {
    return new Response(JSON.stringify({ result: { status: 'executed' } }), { status: 200 });
  };

  const onActionDecided = async () => {
    refreshStarted = true;
    await new Promise((r) => setTimeout(r, 30));
    refreshFinished = true;
  };

  const desk = createApprovalDeskHarness(onActionDecided);

  const p1 = desk.handleDecision('act-refresh-1', 'approve');

  // Wait 10ms until API has responded and onActionDecided is in-flight
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(refreshStarted, true);
  assert.equal(refreshFinished, false);

  // Try clicking again during onActionDecided refresh
  const p2 = desk.handleDecision('act-refresh-1', 'approve');
  await p2;

  // Verify second click did not trigger second API call
  assert.equal(desk.getApiCallLog().length, 1, 'Click during onActionDecided must be blocked');

  await p1;
  assert.equal(refreshFinished, true);
  assert.equal(desk.getState().inFlightSize, 0);
});
