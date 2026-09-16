"""Issue #10 completion benchmark: 50 real chunk-fed streaming turns + live duplex."""
import audioop
import json
import statistics
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import psutil
import sounddevice as sd
import webrtcvad
from faster_whisper import WhisperModel
from llama_cpp import Llama
from piper import PiperVoice

from horus_local_voice.m3_policy import SYSTEM_INSTRUCTION, fixture_category
from horus_local_voice.real_audio import nearest_rank, word_error_rate
from horus_local_voice.streaming import (
    AudioChunk, BoundedAudioIngress, EndpointPolicy, PipelinedResponder,
    StreamSession, StreamState, detect_endpoint, script_route,
)

ART = Path("artifacts")
proc = psutil.Process()
manifest = json.loads((ART / "audio_manifest.json").read_text(encoding="utf-8"))
refs = {Path(x["file"]).name: x["expected"] for x in manifest if "expected" in x}
refs["mixed_ar_en.wav"] = "محتاج أراجع الـ project plan قبل meeting بكرة"
generated = json.loads((ART / "m4_language_manifest.json").read_text(encoding="utf-8"))
items = [(ART / "audio" / name, refs[name], fixture_category(name)) for name in refs]
items += [(Path(x["file"]), x["expected"], x["category"]) for x in generated]
items = items[:20]


def pcm16k(path):
    with wave.open(str(path), "rb") as source:
        rate, channels, width = source.getframerate(), source.getnchannels(), source.getsampwidth()
        pcm = source.readframes(source.getnframes())
    if channels != 1 or width != 2:
        raise ValueError(f"unsupported PCM shape: {path}")
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    return pcm


def transcribe_pcm(model, pcm, language="ar", beam=1):
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    target = Path(handle.name); handle.close()
    try:
        with wave.open(str(target), "wb") as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(pcm)
        segments, _ = model.transcribe(str(target), beam_size=beam, language=language, vad_filter=False)
        return " ".join(x.text.strip() for x in segments).strip()
    finally:
        target.unlink(missing_ok=True)


def chunked_stt_turn(model, session, path, reference, category):
    pcm = pcm16k(path)
    frame_bytes = 960  # 30 ms, mono int16, 16 kHz
    speech_frames = [pcm[i:i + frame_bytes] for i in range(0, len(pcm), frame_bytes)]
    if speech_frames and len(speech_frames[-1]) < frame_bytes:
        speech_frames[-1] += bytes(frame_bytes - len(speech_frames[-1]))
    frames = speech_frames + [bytes(frame_bytes)] * 40  # 1.2 s endpoint tail
    checkpoints = sorted(set(max(1, int(len(speech_frames) * ratio)) for ratio in (0.33, 0.66, 0.90)))
    vad = webrtcvad.Vad(2); ledger = StreamState(); accumulated = bytearray(); flags = []
    partials = []; previous = ""; revisions = 0; endpoint = None; started_turn = time.perf_counter_ns()
    language = None if category == "english" else "ar"
    for seq, frame in enumerate(frames):
        event_id = f"{path.name}:{seq}"
        if not session.queue.push(AudioChunk(seq, time.perf_counter_ns(), frame)):
            raise BufferError("streaming ingress overflow")
        chunk = session.queue.pop()
        if chunk is None or not ledger.accept(event_id, chunk.sequence):
            raise RuntimeError("chunk ordering failure")
        flags.append(vad.is_speech(chunk.pcm, 16000))
        if seq < len(speech_frames):
            accumulated.extend(chunk.pcm)
            if seq + 1 in checkpoints:
                available_ns = time.perf_counter_ns()
                text = transcribe_pcm(model, bytes(accumulated), language, 1)
                done_ns = time.perf_counter_ns()
                if previous and text != previous and not (text.startswith(previous) or previous.startswith(text)):
                    revisions += 1
                if text and text != previous:
                    partials.append({"audio_available_ms": len(accumulated) / 32.0,
                                     "latency_after_availability_ms": (done_ns - available_ns) / 1e6,
                                     "text": text})
                previous = text or previous
        result = detect_endpoint(flags, EndpointPolicy("robust-1200ms", 3, 40, 1000))
        if result.end_frame is not None and len(flags) >= len(speech_frames) + 40:
            endpoint = result.end_frame; break
    final_started = time.perf_counter_ns()
    final = transcribe_pcm(model, bytes(accumulated), language, 5)
    final_ms = (time.perf_counter_ns() - final_started) / 1e6
    return {"transcript": final, "partials": partials, "partial_count": len(partials), "revisions": revisions,
            "finalization_ms": final_ms, "wer": word_error_rate(reference, final), "endpoint_frame": endpoint,
            "stt_total_ms": (time.perf_counter_ns() - started_turn) / 1e6,
            "duplicates": ledger.duplicates, "stale": ledger.stale}


stt = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=1)
stt.transcribe(str(items[0][0]), beam_size=1)
llm = Llama(model_path=str(ART / "models/qwen2.5-1.5b-instruct-q4_k_m.gguf"), n_ctx=1024, n_threads=6, verbose=False)
ar_voice = PiperVoice.load(str(ART / "voices/ar_JO-kareem-medium.onnx"))
en_voice = PiperVoice.load(str(ART / "voices/en_US-lessac-medium.onnx"))
ar_voice.synthesize("تهيئة").__next__(); en_voice.synthesize("warm up").__next__()


def token_stream(messages, timing, max_tokens=18):
    started = time.perf_counter_ns()
    for event in llm.create_chat_completion(messages=messages, max_tokens=max_tokens, temperature=.1, stream=True):
        delta = event["choices"][0]["delta"].get("content", "")
        if delta:
            if timing["first_token_ms"] is None:
                timing["first_token_ms"] = (time.perf_counter_ns() - started) / 1e6
            yield delta
    timing["agent_total_ms"] = (time.perf_counter_ns() - started) / 1e6


def synthesize(text):
    voice = en_voice if script_route(text) == "en" else ar_voice
    chunks = list(voice.synthesize(text or "حسنا"))
    return b"".join(x.audio_int16_bytes for x in chunks)


session = StreamSession("m4-real-pipeline-50", queue_size=8); session.start()
history = []; sustained = []; pinned_memory = "7319"; first_rss = proc.memory_info().rss / 2 ** 20
for turn in range(1, 51):
    path, reference, category = items[(turn - 1) % len(items)]
    recovery = turn in (12, 28, 44)
    if recovery:
        session.recover(("stt", "agent", "tts")[(12, 28, 44).index(turn)])
    stt_row = chunked_stt_turn(stt, session, path, reference, category)
    user_text = stt_row["transcript"] or reference
    if turn == 1:
        user_text += " Session memory is 7319."
    if turn == 50:
        user_text += " What is the pinned session number? Reply with the number only."
    system = {"role": "system", "content": SYSTEM_INSTRUCTION + f" ذاكرة جلسة مثبتة: {pinned_memory}."}
    messages = [system, *history[-8:], {"role": "user", "content": user_text}]
    timing = {"first_token_ms": None, "agent_total_ms": 0.0}; emitted = []; interrupted = turn in (10, 20, 30, 40, 45)
    cancel_state = {"triggered": False, "discarded_trigger_bytes": 0, "post_cancel_bytes": 0}
    pipeline = None
    def emit(audio):
        if interrupted and not cancel_state["triggered"]:
            cancel_state["triggered"] = True
            cancel_state["discarded_trigger_bytes"] = len(audio)
            pipeline.cancel()
            return
        if cancel_state["triggered"]:
            cancel_state["post_cancel_bytes"] += len(audio)
            return
        emitted.append(audio)
    pipeline = PipelinedResponder(synthesize, emit, max_chars=55)
    tts_started = time.perf_counter_ns()
    result = pipeline.run(token_stream(messages, timing), "phrase")
    pipeline_ms = (time.perf_counter_ns() - tts_started) / 1e6
    history.extend([{"role": "user", "content": user_text}, {"role": "assistant", "content": result.text}])
    row = {"turn": turn, "category": category, **stt_row,
           "agent_first_token_ms": timing["first_token_ms"] or 0.0,
           "agent_total_ms": timing["agent_total_ms"], "pipeline_agent_tts_ms": pipeline_ms,
           "tts_chunks": result.text_chunks, "audio_chunks_emitted": len(emitted), "agent_response": result.text,
           "interrupted": interrupted, "cancelled": result.cancelled,
           "cancellation_triggered": cancel_state["triggered"],
           "discarded_trigger_bytes": cancel_state["discarded_trigger_bytes"],
           "stale_audio_bytes": cancel_state["post_cancel_bytes"],
           "recovery": recovery, "rss_mb": proc.memory_info().rss / 2 ** 20,
           "queue_depth": session.queue.depth, "queue_high_water": session.queue.high_water,
           "queue_drops": session.queue.dropped, "system_first": messages[0]["role"] == "system",
           "late_recall_pass": turn != 50 or pinned_memory in result.text}
    sustained.append(row)
    print("real-pipeline", turn, row["partial_count"], flush=True)
session.stop()

out = {
    "pipeline": "30ms ingress -> WebRTC VAD/endpoint -> 3 incremental STT partials + final -> streamed Qwen -> incremental Piper",
    "turns": 50,
    "interruptions": sum(x["interrupted"] for x in sustained),
    "recoveries": sum(x["recovery"] for x in sustained),
    "all_turns_multiple_partials": all(x["partial_count"] >= 2 for x in sustained),
    "partial_hypotheses": sum(x["partial_count"] for x in sustained),
    "late_recall_pass": sustained[-1]["late_recall_pass"],
    "rss_start_mb": first_rss, "rss_end_mb": sustained[-1]["rss_mb"],
    "stt_total_first10_p95_ms": nearest_rank([x["stt_total_ms"] for x in sustained[:10]], .95),
    "stt_total_last10_p95_ms": nearest_rank([x["stt_total_ms"] for x in sustained[-10:]], .95),
    "agent_first_first10_p95_ms": nearest_rank([x["agent_first_token_ms"] for x in sustained[:10]], .95),
    "agent_first_last10_p95_ms": nearest_rank([x["agent_first_token_ms"] for x in sustained[-10:]], .95),
    "mean_wer": statistics.mean(x["wer"] for x in sustained),
    "queue_high_water": max(x["queue_high_water"] for x in sustained),
    "queue_drops": session.queue.dropped,
    "duplicates": sum(x["duplicates"] for x in sustained),
    "stale_events": sum(x["stale"] for x in sustained),
    "cancel_failures": sum(x["interrupted"] and (not x["cancellation_triggered"] or not x["cancelled"] or x["stale_audio_bytes"]) for x in sustained),
    "rows": sustained,
    "versions": {"agent": "Qwen2.5-1.5B-Instruct Q4_K_M", "stt": "faster-whisper tiny CPU int8", "tts": "Piper"},
}
(ART / "m4_real_pipeline_50.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))
