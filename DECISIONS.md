# Decisions

## D-001 — GitHub is the shared coordination channel

Accepted. Issues and PRs are the source of project instructions and review feedback.

## D-002 — Milestone 1 is research/specification only

Accepted. No product implementation, external integration, billing, or existing HORUS runtime changes belong in this PR.

## D-003 — Official Calling API is conditional, not assumed

Meta documents a WhatsApp Business Calling API for VoIP call initiation and receipt.[1] We select it as the candidate production path only after account eligibility, permissions, review, and live-media contract are verified. We do not infer availability from documentation alone.

## D-004 — Local audio harness before channel integration

Accepted. It isolates speech/agent/barge-in behavior from WhatsApp approval and reduces cost and risk.

## D-005 — Reject private WhatsApp protocol automation

Accepted. It is not the default architecture because it creates policy, reliability, account, and security risk.

## D-006 — Fallback is a first-class path

Accepted. Text and voice-note handling share the session contract and are used when realtime calling is unavailable.

[1] https://developers.facebook.com/docs/whatsapp/cloud-api/calling
