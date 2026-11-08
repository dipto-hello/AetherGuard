# 04 Technical Requirements — AetherGuard

**Status:** intended architecture with an implemented synthetic prototype. See [review status](REVIEW_STATUS.md) for verified behavior and remaining gaps; actual deployment controls remain to be selected and verified.

## System boundaries

Trusted operator/task scope → AI agent → MCP client → governance boundary → MCP sandbox tool → synthetic storage → audit/inspector. The agent and ticket cannot authorize themselves; the boundary authenticates the caller, validates actual arguments, scope, order state and policy before any write. Keep sandbox write capability out of the agent and browser.

**Early MCP spike:** during the first build slice use an official SDK and compatible client to exercise `tools/list` and governed `tools/call` through a real boundary, including one allowed and one denied sandbox action. An MCP server alone does not demonstrate interception, and an application-level approval is not automatically MCP-native approval. The current standard bindings are stdio and Streamable HTTP; UI event SSE is separate. See [MCP transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports) and [Python SDK](https://py.sdk.modelcontextprotocol.io/whats-new/).

## Safety and reliability

- Unknown tool, invalid parameters, missing trusted scope or unavailable policy must not silently permit writes. Confirm original payment destination and refundable balance from authoritative sandbox state, not model-supplied booleans.
- Exact-action human approval is authenticated, scoped, expiring and single-use. Re-evaluate policy/order before the write; atomic state changes and durable idempotency guard duplicate requests. Timeout may mean unknown upstream outcome and must be reconciled.
- Restrict and audit policy edits, approvals and sandbox reset. Use synthetic fixtures, safe authentication, appropriate host/origin restrictions and server-side secrets for a public demo. Same-process code alone does not prove network isolation.
- Preserve decision evidence with correlation IDs and minimal sanitized fields. Logging is not authorization; an ordinary audit table is not tamper-proof.

## Choices and limits

The prototype uses Python/FastAPI, SQLite and a React/Vite interface. Hosting, identity method, sandbox isolation and persistence remain deployment decisions. Initial product supports only verified tool paths and client versions; other connectors, SQL analysis, taint graphs, cryptographic audit and multi-agent workflows are optional future extensions, not present capabilities.

Contracts and state are described in [05 Schema](05_Schema.md); detailed related design is in [TECHNICAL_DESIGN](TECHNICAL_DESIGN.md). If older notes conflict, this file and 05 Schema capture the current intent; update supporting detail when decisions change.
