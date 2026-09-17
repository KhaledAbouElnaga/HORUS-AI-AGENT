# M6 non-SIP WebRTC media path

`src/horus_local_voice/whatsapp_media.py` now provides the real media boundary for the official WhatsApp Business Calling Cloud API path:

1. A verified `connect` event carries Meta's SDP offer.
2. `LiveCallingCoordinator` creates an `aiortc` WebRTC endpoint, registers an inbound audio listener, generates the local SDP answer, and sends Meta's `pre_accept` then `accept` call-control actions.
3. Decoded inbound PCM is accumulated by WebRTC VAD into utterances, ending after consecutive silence or max duration; each utterance then runs STT → existing HORUS runtime/memory/tools → TTS. The concrete `PipelineVoiceTurnProcessor` resamples inbound audio to 16 kHz and TTS PCM to 48 kHz.
4. `terminate` cancels/closes the existing HORUS call session and closes the peer connection.

Install the optional live-media dependencies with `requirements-m6-media.txt` together with the existing `requirements-m3-local.txt`. The Graph access token is injected at runtime only; it is not stored, printed, or logged by this repository. No SIP path is used.

The runnable entrypoint is `scripts/run_whatsapp_webhook_server.py`. Its `main()` calls `configure_live_media()` before binding HTTP, so signed `connect` events are dispatched to `LiveCallingCoordinator` rather than the ingress-only adapter. Configure these environment names: `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN`, `HORUS_ROOT`, `STT_MODEL`, `PIPER_AR_VOICE`, and `PIPER_EN_VOICE`; optional names are `STT_COMPUTE_TYPE`, `PIPER_TTS_SAMPLE_RATE`, `META_API_VERSION`, and `WEBHOOK_PORT`.

The runner emits only redacted stage lines: `inbound_audio_started`, `utterance_ready`, `stt_complete`, `horus_turn_complete`, `tts_complete`, `outbound_audio_started`, `outbound_audio_completed`, and `teardown_complete`.

Control-plane failures are staged as `control_sdp_answer`, `control_pre_accept`, or `control_accept` with only status, safe exception type, and HTTP status; raw Graph response bodies are never logged. A failed accept rolls back the provisional `RINGING` marker and event ID so a Meta retry can be accepted again.

## HORUS voice runtime boundary

`LocalHorusPythonPort` keeps memory and tool-session correlation in the HORUS core, but does not import HORUS/Hermes agent modules into the voice virtual environment. `HermesFreeProvider` sends a small JSON request through `scripts/hermes_free_rpc.py`, executed by Hermes' own interpreter (`HERMES_AGENT_PYTHON`, or the installed Hermes venv default). The RPC invokes Hermes' native one-shot runner with the keyless `opencode-free` chain: `nemotron-3-ultra-free`, then `nemotron-3.5-lightning-free`. Subprocess failures are redacted controlled errors; the caller can continue handling subsequent voice work.

A local process-boundary probe from the voice environment is:

```powershell
$env:PYTHONPATH = 'D:\HORUS\HORUS-AI-AGENT\src'
$env:HERMES_AGENT_ROOT = 'C:\Users\khale\AppData\Local\hermes\hermes-agent'
$env:HERMES_AGENT_PYTHON = 'C:\Users\khale\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
& 'D:\HORUS\horus-wa-312\Scripts\python.exe' -c "from horus_local_voice.local_horus_port import LocalHorusPythonPort; p=LocalHorusPythonPort(r'D:\HORUS\horus-core'); print(''.join(p.stream_turn('voice-process-probe','Reply briefly: HORUS VOICE READY',None)))"
```

A real Meta WebRTC negotiation, OPUS/ICE/DTLS-SRTP exchange, and live STT → HORUS → TTS audio remain **NOT MEASURED** until the owner starts a live test call with a runtime process configured with authorized Meta access and a concrete STT/TTS processor.
