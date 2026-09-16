# Milestone 1 Research — WhatsApp Voice Feasibility

**Access date:** 2026-09-16 (UTC)
**Scope:** research/specification only; no Meta account changes, external integration, billing, or runtime changes.

## Findings

Meta's current WhatsApp Business Platform documentation describes a **WhatsApp Business Calling API** for initiating and receiving VoIP calls with WhatsApp users.[1] The platform overview also lists programmatic messaging and calling as Cloud API capabilities.[2]

The Calling documentation's current overview lists voice calling as available and labels video and screen sharing as planned/in development; availability for a specific business account must therefore be verified in Meta's account surfaces before implementation.[1] The documentation navigation exposes configuration, business-initiated calls, user call permissions, user-initiated calls, recording, transcription, SIP, sandbox, App Review, pricing, and troubleshooting sections; this milestone does not assume any of those account entitlements.

Meta webhooks can deliver call events to an HTTPS endpoint. The webhook documentation states that `whatsapp_business_messaging` is needed for messages and calls webhooks, while `whatsapp_business_management` covers other webhook classes.[3] Webhook delivery is asynchronous and Meta retries non-200/failing deliveries for up to seven days.[3]

Cloud API media is message-media infrastructure, not proof of live call-audio streaming. The Media API exposes upload, URL retrieval, download, and deletion; retrieved media URLs expire after five minutes, and incoming media IDs have a seven-day retrieval window.[4] No live RTP/audio-stream contract is claimed here without verifying the Calling/SIP reference and account access.

Meta's Calling App Review guidance requires demonstrating that calling can be enabled/disabled and showing either a business-initiated call or a user-initiated call, including the client UI or calling webhook.[5] This is an approval gate, not something to bypass.

## Capability classification

| Path | Classification | Milestone-1 conclusion |
|---|---|---|
| Meta WhatsApp Business Calling API | Officially supported, subject to account/region/product eligibility and review | Candidate production path; entitlement checklist required |
| Meta Cloud API webhooks for call events | Officially supported webhook mechanism | Candidate control/event path; implement only after review |
| SIP/media bridge | Official documentation area exists, but live media details/account eligibility were not independently verified in this pass | **Unverified gate**; do not design a hard dependency yet |
| WhatsApp Web/private protocol automation | Unsupported/private-client path | Reject as default; ban-risk and policy risk |
| Third-party calling/BSP bridge | Third-party dependency | Alternative only after explicit provider, privacy, cost, and terms review |
| Local browser/phone/audio prototype | Local-only prototype | Preferred first technical validation; no WhatsApp integration |
| Voice notes/text fallback | Official messaging/media primitives, not realtime calling | Required fallback architecture |

## Proposed zero-cost research/validation path

1. Use a local deterministic audio harness to validate VAD, streaming STT, agent turn handling, streaming TTS, interruption, session state, and metrics.
2. Keep provider adapters replaceable; default development mode uses local/free components where quality permits.
3. Validate WhatsApp calling eligibility and the exact call/SIP media contract only in a separately approved test account. No credentials belong in this repository.
4. If realtime calling is unavailable, use text plus voice-note fallback through the existing approved channel boundary; do not alter existing HORUS runtime systems in this milestone.

## Open research gates

- Whether the target business account/region has Calling API access.
- Whether business-initiated calling requires user permission/permission-template flow for the target use case; the official documentation separates business-initiated and user-initiated calling flows.[6][7]
- Exact SIP/media negotiation, codec, transport, webhook payloads, concurrency limits, and latency behavior available to the account.
- App Review, business verification, phone-number, policy, and privacy requirements.
- Calling pricing/entitlement terms for the target account; no billing is activated.

## Sources

[1] https://developers.facebook.com/docs/whatsapp/cloud-api/calling
[2] https://developers.facebook.com/docs/whatsapp/cloud-api
[3] https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks
[4] https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media
[5] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/app-review-guidelines
[6] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/business-initiated-calls
[7] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/user-initiated-calls

Pages were retrieved from Meta's official developer documentation on the access date above. Search results and page navigation revealed additional Calling sections, but no unverified details are presented as facts.
