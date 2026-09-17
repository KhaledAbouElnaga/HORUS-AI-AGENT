# M6 Calling Test Report

## SIMULATED replay

`tests/test_whatsapp_calling.py` replays the normalized lifecycle and proves session correlation, teardown, duplicate/stale protection, malformed-event rejection, and identity-mismatch failure. This evidence is explicitly **SIMULATED**.

## Public ingress

The signed Meta callback path, WABA `calls` subscription, GET challenge, invalid-signature rejection, real incoming delivery, and real terminate delivery have been verified. The tunnel is reversible test infrastructure, not production.

## Live call evidence

Owner-reported live PASS:

- control adapter ingest
- SDP answer
- ICE completion
- `pre_accept` and `accept`
- inbound WhatsApp audio
- STT
- HORUS response
- TTS
- bridge outbound queue placement/dequeue

The caller heard no HORUS audio. Therefore bridge queue completion is not RTP/audibility evidence and Step 7 remains open.

## Root cause and local RTP regression

The old `OutputTrack.recv()` wrapped blocking `queue.Queue.get()` calls in timed `asyncio.to_thread()` futures. Timeout cancelled only the future; abandoned executor threads remained blocked and later stole real TTS PCM. Buffered multi-frame PCM also reached a second defect where `rate` was unbound on the next frame, which could terminate aiortc's RTP sender.

The fixed output track has one paced non-blocking consumer, emits mono signed 16-bit PCM as 960-sample / 20 ms frames at 48 kHz, advances PTS by 960 with `time_base=1/48000`, validates negotiated outbound direction, and records the first negotiated audio codec without logging SDP. A deterministic two-peer aiortc loopback receives decoded non-zero audio and verifies increasing outbound RTP packet and byte counters.

## Remaining live gate

One owner-initiated call must show `outbound_pcm_consumed`, increasing `outbound_rtp_stats`, and audible HORUS speech at the WhatsApp caller. Until all three pass, outbound live audio and Roadmap Step 7 remain **NOT VERIFIED**.
