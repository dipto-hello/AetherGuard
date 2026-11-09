# AETHERGUARD — CURRENT RECOVERY EXPORT VERIFICATION MANIFEST

**Export Identifier**: `AetherGuard_CURRENT_BACKUP`  
**Generated At**: 2026-11-09T10:11:59.655473+00:00  
**Canonical Directory**: `C:\Users\sarke\Downloads\Hackathon and competition\Internatinal AI builder congress hackathon\AetherGuard`  
**Base Git Commit**: `5668653` (`chore: expand gitignore secrets and credentials filters`)  
**Working Tree Status**: Verified Final Security Remediation (A1, A2, A3 + Pre-Scope Decoupling) uncommitted in canonical tree  
**Total Archived Files**: 158 (including SHA256SUMS.txt and this manifest)  

---

## 1. Verified Remediation Features Included

1. **Pre-Scope Order Protection & Sensitive Data Minimization (`core.py`)**:
   - Parsers (`_parse_ticket_synthetic` and `_parse_ticket_llm`) never query database order state before task-scope authorization.
   - Authoritative destination enrichment strictly deferred until after positive scope validation.
   - Blocked requests sanitize raw destinations to None and omit order state.
   - Instrumented `get_order()` assertions confirm ZERO unauthorized database reads.

2. **Trusted MCP Caller Identity Authentication (`mcp_server.py`)**:
   - Client argument `caller_id` never accepted as authentication.
   - Server-verified principal bound to task scope.
   - Rejects anonymous, missing, mismatched, or spoofed caller identities.

3. **MCP Refund Authorization Boundary (`mcp_server.py`)**:
   - Scope possession alone does not grant authority.
   - Enforces policy availability, tool allowlist membership, caller-to-scope ownership, remaining budget, and fail-closed audit protection.

4. **Additional Hardened Safeguards**:
   - Synchronous double-click lock in `frontend/src/components/ApprovalDesk.tsx`.
   - Bounded request-body streaming (`request.stream()`) in `backend/app/main.py`.
   - Zero-leakage audit logging failure protection in `backend/app/governance/mcp_server.py`.

---

## 2. Test Execution & Evidence Status

- **Backend Full Pytest**: **272 / 272 PASSED** (17.29s) — Includes all regression, empirical, adversarial, minimization, and invariant suites.
- **Standalone Approval Check**: **6 / 6 PASSED** (0.006s)
- **Frontend Node Tests**: **9 / 9 PASSED** (274ms)
- **Frontend Vite Build**: Clean build, 0 errors (2067 modules, 285 kB bundle).
- **Evaluation Runner**: **10 / 10 cases passed (100.0% accuracy, 0% FPR)**.
- **SQLite Database**: `aetherguard.db` integrity verified (`('ok',)`).

---

## 3. Critical Source File SHA-256 Checksums

| File Path | SHA-256 Checksum |
| :--- | :--- |
| `backend/app/agent/core.py` | `1aecde409618629a7763b9b761299060977c9e961910eaf3487dc2431d403806` |
| `backend/app/governance/mcp_server.py` | `5c83650539c07560509d84000d6d9aff69330f0dfbfaabac45f9dd4e55410601` |
| `backend/app/mcp_entrypoint.py` | `2f3befde7128538b9e70998e11056975c43bf99adde52c6e02428026a29cbea4` |
| `backend/app/main.py` | `a7a7ec7f6da771ea8c2ffd31fc6b90adbdb94867df4a56672646477b50546854` |
| `backend/app/sandbox/db.py` | `0aa9c8968e5db85b92aabc58c315a7df93a96f8cad940a3d5a98e57e04aa61bf` |
| `backend/tests/test_agent_trace_minimization_regressions.py` | `244e5aba1ff09bf5bee52e3fa1913b58e85c8ef511ca052ec4e64f1c549d5ede` |
| `backend/tests/test_mcp_security_remediation_final.py` | `9926694d3cb8c2cccbff2516aa4bf09f69f7744490c8eb2486b5f90c817b9f8b` |
| `backend/tests/test_adversarial_lookup_order.py` | `b20f923052ac87e4c46089ca15a9eb990aa8340d4a2471412beb11a343de23b7` |
| `backend/tests/test_challenger_m2_recheck_deep_empirical.py` | `ab71641c5e6912e14d592aa7e1f0a47906aa0f2b60f4718f3c5b8ba23453e942` |
| `backend/tests/test_challenger_m2_1_mcp_empirical.py` | `dbf507a05c9fed7e6d85cf4b5dcbc599f97e01f681fc0a56ae72517be6506f17` |
| `backend/tests/test_m2_remediation_regressions.py` | `fadebaf730b59bd82d2288056a2427f820608bea7c869250e02b19a59d48ac4d` |
| `backend/tests/test_mcp_boundary.py` | `6e92f60badc85bdbae6cb6d29344ea6db4100b5e7ce5101cd59c0b22e2c31225` |
| `backend/tests/test_mcp_stdio_e2e.py` | `3df383d06ac50a10e0864609720fdea51b3ecf40d1d3670b25a21b8152d4f656` |
| `frontend/src/components/ApprovalDesk.tsx` | `c4985c55bef3df9f363a96c1c9c9e6cbc9615a439ed978fd49808ec781db2995` |
| `frontend/src/api.ts` | `ce52101c7d89a266f724dc77dc3e12db7535739ca5763affbf3f5163e8c53183` |
| `docs/TEST_EXECUTION_EVIDENCE.md` | `85b83f5f68f33c78fe165308e5f0060ecfc17a87c16c1adb74c8a6df60a925db` |
| `docs/GIT_POST_FIX_REMEDIATION.diff` | `a9fea2226301b5b02e389af2999d1a948f1dec277efa6b2cb57e8578fe27b0fe` |
| `brain/SAFE_WORKSPACE_CLEANUP_PLAN.md` | `2a8f0f3141b655377ac4f521b1d290a94b2b9b256692227d12bdd33114474b33` |
| `brain/POST_AUDIT_VALIDATION_AND_REMAINING_GAPS.md` | `58e2f40f28309ca6a8cb7e6444467084aa5f9ba738d243e668f8ce1ae0d1ff89` |
| `brain/AETHERGUARD_DEEP_AUDIT_AND_ROAST_REPORT.md` | `2a14289972e343694a1b298e3cb53baa6545b7d738057e4a2e847e743f2675bd` |

---

## 4. Exclusion & Sanitization Guarantee

- [x] Zero `.env` files containing actual secrets or tokens included.
- [x] Zero private API keys, credentials, or private certificates included.
- [x] Virtual environments (`.venv`, `venv`) completely excluded.
- [x] Node modules (`node_modules`) completely excluded.
- [x] Build caches (`__pycache__`, `.pytest_cache`, `.vite`) completely excluded.
- [x] Database: Synthetic sandbox data only (`aetherguard.db`), zero customer personal data.
