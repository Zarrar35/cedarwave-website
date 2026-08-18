# Store Billing — Pre‑work (Draft, no production enablement)

Scope:
- Define candidate products/entitlements and identifiers
- Gate all client UI and purchase flows behind feature flags
- Scaffold server‑side receipt/entitlement validation for App Store and Play
- Sandbox‑only tests; no production keys or charging

Requirements and constraints:
- Billing is owner‑gated. Keep all purchase surfaces disabled in production builds.
- No raw card/bank credentials — use store‑native purchase flows.
- Do not publish store listings or pricing until owner approval.

Artifacts in this folder:
- `products.example.json`: Draft schema for products/entitlements and platform SKUs
- `entitlements.example.json`: Mapping from validated purchases to in‑app capability flags
- `test-plan.md`: Sandbox test cases and expected outcomes

Server validation (scaffold only):
- Apple App Store Server API: signed JWS receipts, subscription status, refund events
- Google Play Developer API: purchase tokens, signatures, subscription status
- Webhook intake: signed provider callbacks; queue/idempotency; audit logs

Client gating (scaffold only):
- Feature flags for Premium surface visibility and purchase affordances
- Purchase flow behind flags; show non‑interactive preview when disabled
- Receipt sync on sign‑in and foreground; offline cache with expiry

Security/abuse:
- Validate signatures, verify bundle/package names and app identifiers
- Bind entitlements to account + device where applicable
- Monitor for chargebacks/refunds; revoke entitlements accordingly

Do not include secrets or production keys in this repo.

