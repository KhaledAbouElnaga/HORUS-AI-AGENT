# Threat Model

## Assets

Conversation audio/transcripts, owner identity, session memory, tool credentials (kept outside this repo), tool side effects, channel account, and service availability.

## Trust boundaries

1. WhatsApp/Meta channel to channel adapter.
2. Untrusted audio/text to STT and agent runtime.
3. Agent runtime to tool executor.
4. Runtime telemetry/logs to operators.
5. Repository/CI to deployment environment.

## Threats and controls

| Threat | Control |
|---|---|
| Spoofed caller or replayed event | Verify channel signatures, event IDs, timestamps, session binding, and authorization before acceptance |
| Prompt injection in speech/text | Treat content as data; separate system/tool policy from conversation; require tool allowlists and confirmation policy |
| Unauthorized or dangerous tool action | Typed schemas, least privilege, validation, dry-run, timeouts, cancellation, audit, and fail-closed defaults |
| Audio/transcript leakage | Minimize retention, encryption in transit/at rest, redaction, access control, and recording off by default |
| Secret exposure | Environment/vault injection only; `.gitignore`; secret scanning; never log tokens/cookies/keys |
| Barge-in race causing unintended action | Cancel current generation/tool boundary and use idempotency keys before side effects |
| Webhook replay/duplication | Persist event IDs with TTL and process idempotently |
| Provider/channel outage | Health state, bounded retries, circuit breaker, and honest text/voice-note fallback |
| Ban/policy risk from private automation | Do not use private WhatsApp protocols as the default or production path |
| Cost runaway | Free/local defaults, quotas, explicit disabled paid adapters, budget alarms where applicable |

## Security acceptance boundary

No production integration is approved until identity/authentication, privacy/retention, tool authorization, webhook verification, policy/terms, and cost gates have written evidence.
