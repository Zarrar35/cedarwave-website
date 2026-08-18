# Push and Deep‑Link Routing — Pre‑work (Draft, no production push)

Scope:
- Complete in‑app routing and link handling (tracked in Roofmates PR #30)
- Prepare association files (AASA and Android asset links) as templates
- Token lifecycle: registration, rotation, revocation; user opt‑in UI
- Sandbox‑only APNs/FCM tests; no production keys or delivery

Artifacts in this folder:
- `apple-app-site-association.template.json`
- `assetlinks.template.json`
- `sandbox-test-plan.md`

Do not place active association files at site root or `/.well-known/` until owner approval.

Token lifecycle checklist:
- Store encrypted tokens server‑side; do not leak in client logs
- Bind tokens to account and device identifiers (non‑PII)
- Remove tokens on sign‑out and account deletion
- Handle provider invalidation feedback for silent revocation

Deep‑link patterns (examples; finalize with app team):
- `https://cedarwavetechnologies.com/rm/*`
- `https://cedarwavetechnologies.com/roofmates/*`

Security:
- Serve association files over HTTPS only
- Validate signatures where applicable; least‑privilege push keys

