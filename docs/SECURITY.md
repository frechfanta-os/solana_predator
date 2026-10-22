# Security Boundary & Compliance Specification — SOLANA PREDATOR

## 1. Absolute Security Boundaries

SOLANA PREDATOR is an observational and simulated trading terminal. The following security controls are architecturally hardcoded into the codebase:

1. **Read-Only RPC Access**:
   - The RPC client only implements read methods (`getSlot`, `getTransaction`, `logsSubscribe`, etc.).
   - No `sendTransaction`, `sendRawTransaction`, or transaction signing methods exist in the codebase.
   - Verified by automated AST and regex source code scans in `backend/tests/test_security_boundary.py`.

2. **Zero Key Management**:
   - The application does not store, accept, parse, or generate private keys or mnemonic seed phrases.
   - No wallet connect or signature authorization dialogs exist in the frontend.

3. **Separate Paper Component**:
   - The `PaperBroker` operates exclusively on in-memory and database virtual records.
   - There is no code path or configuration flag that can convert the paper broker into a live trading router.

4. **Mandatory UI Disclaimer**:
   - The banner `LIVE MARKET DATA — PAPER TRADING ONLY` is permanently mounted at the top of the terminal.

5. **Administrative Route Protection**:
   - State-changing administrative endpoints (such as `/api/simulation/start_replay` and `/api/paper/reset`) require a valid `X-Admin-Key` header.
   - Unauthenticated mutations return HTTP 401 Unauthorized.
