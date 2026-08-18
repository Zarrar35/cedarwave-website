# Push/Deep‑Link Sandbox Test Plan (Draft)

Goals:
- Validate deep‑link routing and sandbox push delivery without production keys.

Preconditions:
- App implements link routing for `/rm/*` and `/roofmates/*` (PR #30)
- Staging server issues sandbox notifications (APNs dev, FCM test)
- Feature flags for push opt‑in and notification categories

Deep‑link tests:
1) Cold‑start open to specific screen (Event, Pool, Expense)
2) Foreground routing from universal link
3) Back‑stack behavior and parameter parsing

Push tests (sandbox):
1) Registration and token upload
2) Foreground receipt and UI handling
3) Background receipt opens correct route
4) Token rotation and invalidation handling

Security and privacy:
- No PII in push payloads; use identifiers resolved client‑side after auth
- Enforce user notification preferences and per‑scope visibility

No production keys. Do not deploy association files.

