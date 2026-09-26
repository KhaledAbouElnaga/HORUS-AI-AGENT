# M6 Calling Test Report

## SIMULATED replay

`tests/test_whatsapp_calling.py` replays the normalized lifecycle and proves session correlation, teardown, duplicate/stale protection, malformed-event rejection, and identity-mismatch failure. This evidence is explicitly **SIMULATED**.

## Public ingress

The signed Meta callback path, WABA `calls` subscription, GET challenge, invalid-signature rejection, real incoming delivery, and real terminate delivery have been verified. The tunnel is reversible test infrastructure, not production.

## Current live result

Owner-reported live transport PASS: control acceptance, ICE, inbound audio, STT, HORUS response, TTS, negotiated Opus/sendrecv, OutputTrack consumption, RTP packet/byte transmission, and caller-heard HORUS audio. The remaining failure is conversational: low-confidence Arabic-as-English detection, fragmented endpointing, possible TTS echo, and stale 9–17 second provider turns. Step 7 remains open until one clear Arabic question receives one semantically relevant Arabic answer.

## Root cause and local RTP regression

The old `OutputTrack.recv()` wrapped blocking `queue.Queue.get()` calls in timed `asyncio.to_thread()` futures. Timeout cancelled only the future; abandoned executor threads remained blocked and later stole real TTS PCM. Buffered multi-frame PCM also reached a second defect where `rate` was unbound on the next frame, which could terminate aiortc's RTP sender.

The fixed output track has one paced non-blocking consumer, emits mono signed 16-bit PCM as 960-sample / 20 ms frames at 48 kHz, advances PTS by 960 with `time_base=1/48000`, validates negotiated outbound direction, and records the first negotiated audio codec without logging SDP. A deterministic two-peer aiortc loopback receives decoded non-zero audio and verifies increasing outbound RTP packet and byte counters.

## Remaining live gate

One owner-initiated call must show the new endpointing/turn stages and deliver one clear, semantically relevant Arabic answer to a clear Arabic question. Until that passes, conversational live quality and Roadmap Step 7 remain **NOT VERIFIED**.
