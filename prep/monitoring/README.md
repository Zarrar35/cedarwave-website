# Monitoring and Kill Switches — Pre‑work (Draft)

Objectives:
- Visibility into billing validation, entitlement state changes, and push delivery
- Safe rollback/disable paths without app updates

Suggested controls:
- Feature flags: `premiumEnabled`, `pushEnabled`, category‑level push flags
- Server toggles: entitlement grant/refresh disable, webhook intake pause
- Circuit breakers for provider error spikes

Metrics and alerts:
- Purchase attempts, validation success/failure rates
- Entitlement grant/revoke counts
- Push token registrations, invalidations, delivery outcomes

Logging:
- Structured, privacy‑safe logs with correlation IDs
- Audit trails for admin actions and entitlement changes

Do not wire production alerts until owner approval.

