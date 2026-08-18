# Billing Sandbox Test Plan (Draft)

Goals:
- Verify basic purchase, restore, refund, and entitlement behaviors in sandbox environments.

Preconditions:
- Feature flags enabled for sandbox builds only
- Test store accounts configured (Apple sandbox, Play test users)
- Backend receipt validation endpoints reachable in staging

Test cases:
1) First‑time purchase (monthly)
   - Expect purchase success, receipt stored, entitlement `premium_core` granted
2) Restore purchases on new device
   - Expect entitlement restored after validation
3) Expiry (monthly)
   - After simulated expiry, entitlement revoked after grace period
4) Refund/chargeback
   - Provider webhook triggers entitlement revocation
5) Canceled subscription
   - Entitlement remains until end of period, then revocation
6) Purchase failure/decline
   - No entitlement granted; UI shows retry and help

Logging and monitoring:
- Client: purchase result, receipt status, flag state
- Server: validation outcome, entitlement grant/revoke, webhook audit

No production keys. No public store listing changes.

