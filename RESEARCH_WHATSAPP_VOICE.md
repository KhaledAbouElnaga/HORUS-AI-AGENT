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

## Official Calling media-path verification

The current official SIP page documents Meta-to-SIP signaling, TLS, digest authentication, and an SDP offer supporting ICE, DTLS-SRTP, and OPUS (WebRTC-style media).[8] It also documents `calls`/SIP lifecycle webhooks and says SIP is enabled per business phone number; enabling SIP makes that number use SIP signaling rather than Graph call control.[8]

The Calling overview documents inbound and business-initiated flows.[1] Call settings documents that calling is disabled by default and requires a daily messaging limit of at least 2,000 unique recipients.[9]

The official pricing page says user-initiated calls are free, while business-initiated calls are charged by duration, destination country, and volume tier; it also states a valid payment method is required for calls.[10] Therefore business-initiated production calling is explicitly outside the zero-billing bootstrap.

**Verified boundary:** the public docs establish SIP/SDP/OPUS at the protocol level, but do not establish this account's entitlement, negotiated codec behavior in production, regional availability, quotas, or an end-to-end test endpoint. Those require account access/approval and remain HUMAN GATES. No SIP password or account setting was requested or changed.

## Concrete local pipeline candidates

| Stage | Candidate | Windows/local | Streaming + Arabic/Egyptian considerations | Resources/license/cost |
|---|---|---|---|---|
| VAD/turn | Silero VAD | PyTorch/ONNX local; Windows viable | Streaming examples; broad multilingual/noisy-audio training, but Egyptian turn thresholds need tuning.[11] | CPU-friendly small model; MIT; local/free |
| VAD alternative | WebRTC VAD | Native Python bindings/Windows viable | Frame-based low latency; less robust than Silero for varied Arabic/noise; tune aggressiveness | Very small CPU footprint; permissive BSD-style; local/free |
| STT | whisper.cpp + Whisper model | Explicit Windows/MSVC and CPU support; MIT implementation.[12] | Incremental stream example exists; multilingual Whisper handles Arabic, but Egyptian dialect WER must be measured | CPU/GPU model-size tradeoff; MIT code, model terms must be checked; local/free |
| STT alternative | faster-whisper | Windows via Python/CTranslate2; local | Streaming wrapper/policy is needed; strong Whisper baseline, dialect quality still benchmarked.[13] | More RAM/compute than tiny native path; MIT; local/free |
| Agent runtime/tools | llama.cpp server + existing HORUS-compatible adapter | Windows CPU/GPU; local | Token streaming; Arabic quality depends on selected local model; tool schemas and allowlist stay deterministic.[15] | Model-dependent RAM; MIT code, model license varies; local/free |
| Agent alternative | Existing HORUS runtime adapter | Not changed in M1; interface-compatible future option | Preserves existing routing only after reviewed integration milestone | Existing provider/account terms apply; not activated in M1 |
| TTS | Piper (`piper1-gpl`) | Local Windows binaries/build path possible | Chunked synthesis can stream at sentence/phrase boundaries; Arabic voice availability/voice-model license must be verified per model.[14] | CPU-local; GPL-3.0 code, voice licenses vary; free but license review required |
| TTS alternative | OS/local speech engine adapter | Windows available where installed | Low integration cost, Arabic/Egyptian voice quality and streaming vary by installed voice | Local; OS/voice terms; no account required |
| Interruption | Cancellation controller + VAD side-channel | Pure local application logic | Stop/duck TTS on speech-start; bounded cancellation target is 250 ms p95 | No external cost/license; requires deterministic tests |
| Session/memory | SQLite session store + bounded in-memory ring | Native/local Windows | Versioned turns, TTL, redacted event IDs; no raw audio by default | Standard library/local; no external account |
| Observability | OpenTelemetry SDK + local JSONL/Prometheus-compatible metrics | Local Windows | Histograms for each latency segment and state transitions; redact content/credentials | Local/free; dependency licenses to review |

## Proposed zero-cost research/validation path

1. Use a local deterministic audio harness to validate VAD, streaming STT, agent turn handling, streaming TTS, interruption, session state, and metrics.
2. Keep provider adapters replaceable; default development mode uses local/free components where quality permits.
3. Validate WhatsApp calling eligibility and the exact call/SIP media contract only in a separately approved test account. No credentials belong in this repository.
4. If realtime calling is unavailable, use text plus voice-note fallback through the existing approved channel boundary; do not alter existing HORUS runtime systems in this milestone.

The preferred Milestone-2 prototype stack is **Silero VAD → whisper.cpp (small/base multilingual benchmark) → local llama.cpp-compatible agent adapter → Piper Arabic voice where a suitable licensed voice passes evaluation**, with SQLite and local metrics. faster-whisper remains the STT comparison. This choice minimizes irreversible dependencies, runs on Windows without a paid account, supports streaming-oriented interfaces, and makes Arabic/Egyptian quality measurable before any channel integration.

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
[8] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/sip
[9] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/call-settings
[10] https://developers.facebook.com/docs/whatsapp/cloud-api/calling/pricing
[11] https://github.com/snakers4/silero-vad
[12] https://github.com/ggml-org/whisper.cpp
[13] https://github.com/SYSTRAN/faster-whisper
[14] https://github.com/OHF-Voice/piper1-gpl
[15] https://github.com/ggml-org/llama.cpp

Pages were retrieved from Meta's official developer documentation on the access date above. Search results and page navigation revealed additional Calling sections, but no unverified details are presented as facts.
