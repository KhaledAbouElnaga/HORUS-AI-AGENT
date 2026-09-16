import audioop
import json
import statistics
import tempfile
import time
import wave
from pathlib import Path

import psutil
from faster_whisper import WhisperModel

from horus_local_voice.m3_policy import fixture_category
from horus_local_voice.real_audio import nearest_rank, word_error_rate
from horus_local_voice.streaming import AudioChunk, BoundedAudioIngress, StreamState

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
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
        pcm = w.readframes(w.getnframes())
    if channels != 1 or width != 2:
        raise ValueError(f"unsupported PCM shape: {path}")
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    return pcm


def transcribe_pcm(model, pcm, language, beam):
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    target = Path(handle.name)
    handle.close()
    try:
        with wave.open(str(target), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(pcm)
        segments, _ = model.transcribe(str(target), beam_size=beam, language=language, vad_filter=False)
        return " ".join(x.text.strip() for x in segments).strip()
    finally:
        target.unlink(missing_ok=True)


def run_turn(model, path, reference, category, policy):
    pcm = pcm16k(path)
    frame_bytes = 16000 * 30 // 1000 * 2
    frames = [pcm[i:i + frame_bytes] for i in range(0, len(pcm), frame_bytes)]
    if frames and len(frames[-1]) < frame_bytes:
        frames[-1] = frames[-1] + bytes(frame_bytes - len(frames[-1]))
    ingress = BoundedAudioIngress(max_chunks=max(8, len(frames) + 1))
    ingress.start()
    ledger = StreamState()
    accumulated = bytearray()
    partials = []
    revision_count = 0
    previous = ""
    checkpoints = sorted(set(max(1, int(len(frames) * ratio)) for ratio in policy["ratios"]))
    for seq, frame in enumerate(frames):
        chunk = AudioChunk(sequence=seq, captured_ns=time.perf_counter_ns(), pcm=frame)
        if not ingress.push(chunk):
            raise BufferError("unexpected chunk drop")
        received = ingress.pop()
        if received is None or not ledger.accept(f"input-{received.sequence}", received.sequence):
            raise RuntimeError("stream ordering failure")
        accumulated.extend(received.pcm)
        if len(accumulated) // frame_bytes in checkpoints:
            window = bytes(accumulated)
            if policy["window_seconds"]:
                window = window[-int(16000 * 2 * policy["window_seconds"]):]
            available_ns = time.perf_counter_ns()
            started = time.perf_counter_ns()
            text = transcribe_pcm(model, window, None if category == "english" else "ar", policy["beam"])
            finished = time.perf_counter_ns()
            if previous and text != previous and not (text.startswith(previous) or previous.startswith(text)):
                revision_count += 1
            if text and text != previous:
                partials.append({
                    "audio_available_ms": len(accumulated) / 32.0,
                    "latency_after_availability_ms": (finished - available_ns) / 1e6,
                    "compute_ms": (finished - started) / 1e6,
                    "text": text,
                    "deduped": True,
                })
            previous = text or previous
    final_started = time.perf_counter_ns()
    final = transcribe_pcm(model, bytes(accumulated), None if category == "english" else "ar", policy["final_beam"])
    final_ms = (time.perf_counter_ns() - final_started) / 1e6
    ingress.close()
    return {
        "file": path.name,
        "category": category,
        "chunks_received": len(frames),
        "chunk_ms": 30,
        "partial_count": len(partials),
        "partials": partials,
        "final": final,
        "finalization_ms": final_ms,
        "wer": word_error_rate(reference, final),
        "revisions": revision_count,
        "duplicate_accumulation": False,
        "queue_high_water": ingress.high_water,
        "queue_drops": ingress.dropped,
    }


model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=1)
model.transcribe(str(items[0][0]), beam_size=1)
policies = [
    {"name": "cumulative-33-66-90-beam1", "ratios": (0.33, 0.66, 0.90), "beam": 1, "final_beam": 5, "window_seconds": None},
    {"name": "rolling-3s-25-50-75-beam5", "ratios": (0.25, 0.50, 0.75), "beam": 5, "final_beam": 5, "window_seconds": 3.0},
]
candidates = []
for policy in policies:
    rows = []
    for index, item in enumerate(items, 1):
        rows.append(run_turn(model, *item, policy))
        print(policy["name"], index, flush=True)
    first = [row["partials"][0]["latency_after_availability_ms"] for row in rows if row["partials"]]
    candidates.append({
        "candidate": policy["name"],
        "turns": len(rows),
        "fixed_chunk_ms": 30,
        "partial_hypotheses": sum(x["partial_count"] for x in rows),
        "turns_with_multiple_partials": sum(x["partial_count"] >= 2 for x in rows),
        "first_partial_after_availability_p50_ms": statistics.median(first),
        "first_partial_after_availability_p95_ms": nearest_rank(first, 0.95),
        "final_p50_ms": statistics.median(x["finalization_ms"] for x in rows),
        "final_p95_ms": nearest_rank([x["finalization_ms"] for x in rows], 0.95),
        "mean_wer": statistics.mean(x["wer"] for x in rows),
        "rss_mb": proc.memory_info().rss / 2 ** 20,
        "queue_drops": sum(x["queue_drops"] for x in rows),
        "rows": rows,
    })
(ART / "m4_stt_candidates_chunked.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps([{k: v for k, v in x.items() if k != "rows"} for x in candidates], ensure_ascii=False))
