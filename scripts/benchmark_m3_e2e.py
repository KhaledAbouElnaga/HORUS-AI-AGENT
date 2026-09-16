# Run selected M3 pipeline with explicit language routing and category reporting.
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import psutil
from faster_whisper import WhisperModel
from llama_cpp import Llama
from piper import PiperVoice

from horus_local_voice.m3_policy import ARABIC_VOICE, ENGLISH_VOICE, SYSTEM_INSTRUCTION, fixture_category, inference_context, stt_language_for, tts_voice_for
from horus_local_voice.real_audio import nearest_rank, webrtc_vad_wav, word_error_rate

manifest = json.loads(Path("artifacts/audio_manifest.json").read_text(encoding="utf-8"))
by_name = {Path(item["file"]).name: item for item in manifest}
for item in manifest:
    if "expected" not in item:
        item["expected"] = " ".join(by_name[Path(name).name]["expected"] for name in item["composed_from"])
files = sorted(Path("artifacts/audio").glob("*.wav"))
proc = psutil.Process()

started = time.perf_counter()
stt = WhisperModel("base", device="cpu", compute_type="int8")
stt_load = (time.perf_counter() - started) * 1000
started = time.perf_counter()
agent = Llama(model_path="artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx=2048, n_threads=8, n_gpu_layers=0, verbose=False)
agent_load = (time.perf_counter() - started) * 1000
voices = {}
voice_load_ms = {}
for voice_path in (ARABIC_VOICE, ENGLISH_VOICE):
    started = time.perf_counter()
    voices[voice_path] = PiperVoice.load(str(voice_path))
    voice_load_ms[voice_path.name] = round((time.perf_counter() - started) * 1000, 2)

system = {"role": "system", "content": SYSTEM_INSTRUCTION}
history = []
rows = []
for index in range(30):
    path = files[index % len(files)]
    category = fixture_category(path.name)
    expected = by_name[path.name]["expected"]
    total_started = time.perf_counter()
    vad = webrtc_vad_wav(path)
    stt_language = stt_language_for(category)
    started = time.perf_counter()
    segments, info = stt.transcribe(str(path), language=stt_language, beam_size=5, vad_filter=False)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    stt_ms = (time.perf_counter() - started) * 1000
    history.append({"role": "user", "content": text})
    context = inference_context(system, history)
    stream = agent.create_chat_completion(messages=context, max_tokens=24, temperature=0.1, stream=True)
    started = time.perf_counter()
    first = None
    reply = ""
    for chunk in stream:
        token = chunk["choices"][0]["delta"].get("content", "")
        if token and first is None:
            first = (time.perf_counter() - started) * 1000
        reply += token
    agent_ms = (time.perf_counter() - started) * 1000
    history.append({"role": "assistant", "content": reply})
    voice_path = tts_voice_for(category, reply)
    started = time.perf_counter()
    fallback = "Unable to reply" if voice_path == ENGLISH_VOICE else "تعذر الرد"
    chunks = voices[voice_path].synthesize(reply or fallback)
    first_chunk = next(chunks)
    tts_first = (time.perf_counter() - started) * 1000
    chunk_count = 1
    for _ in chunks:
        chunk_count += 1
    tts_total = (time.perf_counter() - started) * 1000
    rows.append({
        "turn": index + 1, "file": path.name, "category": category,
        "expected": expected, "stt_route": "auto" if stt_language is None else "forced-ar",
        "detected_language": info.language, "wer": word_error_rate(expected, text),
        "tts_voice": voice_path.name, "system_instruction_present": context[0] == system,
        "context_messages": len(context), "vad_ms": vad.latency_ms, "stt_ms": stt_ms,
        "agent_first_token_ms": first or agent_ms, "agent_total_ms": agent_ms,
        "tts_first_audio_ms": tts_first, "tts_total_ms": tts_total,
        "end_to_end_ms": (time.perf_counter() - total_started) * 1000,
        "transcript": text, "reply": reply, "tts_chunks": chunk_count,
    })


def stats(selected, key):
    values = [row[key] for row in selected]
    return {"p50": round(statistics.median(values), 2), "p95": round(nearest_rank(values, 0.95), 2), "min": round(min(values), 2), "max": round(max(values), 2)}


metric_names = ["vad_ms", "stt_ms", "agent_first_token_ms", "tts_first_audio_ms", "end_to_end_ms"]
category_metrics = {}
for category in ("egyptian_arabic", "msa_arabic", "english", "mixed"):
    selected = [row for row in rows if row["category"] == category]
    category_metrics[category] = {
        "turns": len(selected), "mean_wer": round(statistics.mean(row["wer"] for row in selected), 4),
        **{key: stats(selected, key) for key in metric_names},
        "stt_routes": dict(Counter(row["stt_route"] for row in selected)),
        "tts_voices": dict(Counter(row["tts_voice"] for row in selected)),
    }

out = {
    "turns": 30,
    "pipeline": "WebRTC VAD -> base/int8 policy-routed STT beam5 -> Qwen2.5-1.5B Q4_K_M CPU -> policy-routed Piper",
    "routing_policy": {
        "stt": "English uses auto-detection; Egyptian, MSA, and Arabic-led synthetic mixed use forced Arabic.",
        "tts": "English uses en_US-lessac-medium; Arabic uses ar_JO-kareem-medium; mixed uses reply-dominant script with Arabic tie-break.",
    },
    "cold_load_ms": {"stt": round(stt_load, 2), "agent": round(agent_load, 2), "tts": voice_load_ms},
    "metrics": {key: stats(rows, key) for key in metric_names},
    "mean_wer": round(statistics.mean(row["wer"] for row in rows), 4),
    "category_metrics": category_metrics,
    "system_instruction_retained_all_turns": all(row["system_instruction_present"] for row in rows),
    "rss_mb": round(proc.memory_info().rss / 2**20, 1), "gpu": "not used", "rows": rows,
}
Path("artifacts/m3_e2e_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in out.items() if key != "rows"}, ensure_ascii=False))
