# M6 non-SIP WebRTC media path

`src/horus_local_voice/whatsapp_media.py` now provides the real media boundary for the official WhatsApp Business Calling Cloud API path:

1. A verified `connect` event carries Meta's SDP offer.
2. `LiveCallingCoordinator` creates an `aiortc` WebRTC endpoint, registers an inbound audio listener, generates the local SDP answer, and sends Meta's `pre_accept` then `accept` call-control actions.
3. Decoded inbound PCM is passed to an injected voice-turn processor (STT → existing HORUS runtime/memory/tools → TTS). The concrete `PipelineVoiceTurnProcessor` resamples inbound audio to 16 kHz for the existing STT boundary and TTS PCM to 48 kHz for the WebRTC track.
4. `terminate` cancels/closes the existing HORUS call session and closes the peer connection.

Install the optional live-media dependencies with `requirements-m6-media.txt` together with the existing `requirements-m3-local.txt`. The Graph access token is injected at runtime only; it is not stored, printed, or logged by this repository. No SIP path is used.

The runnable entrypoint is `scripts/run_whatsapp_webhook_server.py`. Its `main()` calls `configure_live_media()` before binding HTTP, so signed `connect` events are dispatched to `LiveCallingCoordinator` rather than the ingress-only adapter. Configure these environment names: `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN`, `HORUS_ROOT`, `STT_MODEL`, `PIPER_AR_VOICE`, and `PIPER_EN_VOICE`; optional names are `STT_COMPUTE_TYPE`, `PIPER_TTS_SAMPLE_RATE`, `META_API_VERSION`, and `WEBHOOK_PORT`.


The control-plane, SDP handoff, bounded duplex queue, duplicate protection, and teardown are regression-tested. A real Meta WebRTC negotiation, OPUS/ICE/DTLS-SRTP exchange, and live STT → HORUS → TTS audio remain **NOT MEASURED** until the owner starts a live test call with a runtime process configured with authorized Meta access and a concrete STT/TTS processor.
