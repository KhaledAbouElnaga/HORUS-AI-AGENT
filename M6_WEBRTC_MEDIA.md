# M6 non-SIP WebRTC media path

`src/horus_local_voice/whatsapp_media.py` now provides the real media boundary for the official WhatsApp Business Calling Cloud API path:

1. A verified `connect` event carries Meta's SDP offer.
2. `LiveCallingCoordinator` creates an `aiortc` WebRTC endpoint, registers an inbound audio listener, generates the local SDP answer, and sends Meta's `pre_accept` then `accept` call-control actions.
3. Decoded inbound PCM is accumulated by WebRTC VAD into utterances, ending after consecutive silence or max duration; each utterance then runs STT → existing HORUS runtime/memory/tools → TTS. The concrete `PipelineVoiceTurnProcessor` resamples inbound audio to 16 kHz and TTS PCM to 48 kHz.
4. `terminate` cancels/closes the existing HORUS call session and closes the peer connection.

Install the optional live-media dependencies with `requirements-m6-media.txt` together with the existing `requirements-m3-local.txt`. The Graph access token is injected at runtime only; it is not stored, printed, or logged by this repository. No SIP path is used.

The runnable entrypoint is `scripts/run_whatsapp_webhook_server.py`. Its `main()` calls `configure_live_media()` before binding HTTP, so signed `connect` events are dispatched to `LiveCallingCoordinator` rather than the ingress-only adapter. Configure these environment names: `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `META_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN`, `HORUS_ROOT`, `PIPER_AR_VOICE`, and `PIPER_EN_VOICE`; optional names are `STT_MODEL` (defaults to `base`), `STT_BEAM_SIZE` (defaults to `5`), `STT_COMPUTE_TYPE`, `PIPER_TTS_SAMPLE_RATE`, `END_SILENCE_MS` (defaults `700`), `PLAYBACK_TAIL_MS` (defaults `800`), `META_API_VERSION`, and `WEBHOOK_PORT`.

The runner emits only redacted stage lines. Outbound stages are intentionally separate: `outbound_pcm_ready` (bridge queue), `outbound_pcm_forwarded` (bridge dequeue), `outbound_pcm_placed` (track queue), `outbound_pcm_consumed` (actual `OutputTrack.recv()` consumption), and `outbound_rtp_stats` (`packets_sent` / `bytes_sent`). Only the last two establish progress beyond the bridge queue, and caller audibility remains the final live acceptance gate. `outbound_media_negotiated` records only safe codec/direction names. During Step 7, bridge half-duplex is driven by actual non-silent `OutputTrack` frame consumption and stays active through an 800 ms tail; `inbound_suppressed_playback` proves that protection was exercised. This deliberately disables barge-in until acoustic echo cancellation is separately implemented. The development endpoint accepts one active call at a time and returns `busy` for a second call, preventing shared media/session state from crossing calls.

Control-plane failures are staged as `control_sdp_answer`, `control_pre_accept`, or `control_accept` with only status, safe exception type, and HTTP status; raw Graph response bodies are never logged. A failed accept rolls back the provisional `RINGING` marker and event ID so a Meta retry can be accepted again.

## Final bilingual STT and TTS routing

Live VAD uses three consecutive voiced 20 ms frames to start, a minimum 800 ms utterance, and 700 ms end silence (both end silence and playback tail can be overridden by safe runtime configuration). This prevents short VAD spikes and normal phone-speech pauses from being dispatched as turns. Each endpointed utterance performs one final `faster-whisper` decode rather than re-decoding prefixes.

The selected CPU configuration is multilingual `base`, `int8`, beam size `5`. High-confidence `ar`/`en` auto decisions are used directly. For unsupported or low-confidence auto language (<0.60), the completed utterance is decoded as both Arabic and English; a deterministic score combines average log probability, no-speech probability, and Arabic/Latin script plausibility. This addresses low-confidence Arabic-as-English without forcing genuine English or mixed speech to Arabic. Cached-fixture median STT latency was tiny `570–640 ms`, base `1,079–1,152 ms`, and small `3,236–3,497 ms`; `base` is the quality/latency balance, while natural bilingual live quality remains a live gate.

TTS chooses the Arabic `ar_JO-kareem` voice only for route `ar` and the English `en_US-lessac` voice only for route `en`. It logs only `tts_route=ar|en` and PCM size, rejects empty PCM, and never logs response text or voice paths.

## HORUS voice runtime boundary

`LocalHorusPythonPort` keeps memory and tool-session correlation in the HORUS core, but does not import HORUS/Hermes agent modules into the voice virtual environment. `HermesFreeProvider` sends a small JSON request through `scripts/hermes_free_rpc.py`, executed by Hermes' own interpreter (`HERMES_AGENT_PYTHON`, or the installed Hermes venv default). The RPC invokes Hermes' native one-shot runner with the keyless `opencode-free` chain: `nemotron-3-ultra-free`, then `nemotron-3.5-lightning-free`. Subprocess failures are redacted controlled errors; the caller can continue handling subsequent voice work.

A local process-boundary probe from the voice environment is:

```powershell
$env:PYTHONPATH = 'D:\HORUS\HORUS-AI-AGENT\src'
$env:HERMES_AGENT_ROOT = 'C:\Users\khale\AppData\Local\hermes\hermes-agent'
$env:HERMES_AGENT_PYTHON = 'C:\Users\khale\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
& 'D:\HORUS\horus-wa-312\Scripts\python.exe' -c "from horus_local_voice.local_horus_port import LocalHorusPythonPort; p=LocalHorusPythonPort(r'D:\HORUS\horus-core'); print(''.join(p.stream_turn('voice-process-probe','Reply briefly: HORUS VOICE READY',None)))"
```

A real live call has verified Meta control acceptance, ICE, inbound audio, STT, HORUS response generation, TTS, and bridge queue handling, but the caller heard no response. Local regression now proves silence → real PCM → paced `OutputTrack` frames → encoded RTP received by a second aiortc peer, with negotiated Opus/outbound direction and non-zero sender packet/byte counters. Caller audibility remains **NOT MEASURED** until the next owner-initiated live call.
