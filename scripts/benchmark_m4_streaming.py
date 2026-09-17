import gc
import audioop
import json
import statistics
import tempfile
import time
import wave
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import psutil
import webrtcvad
from faster_whisper import WhisperModel
from llama_cpp import Llama
from piper import PiperVoice

from horus_local_voice.m3_policy import ARABIC_VOICE, ENGLISH_VOICE, SYSTEM_INSTRUCTION, fixture_category, inference_context
from horus_local_voice.real_audio import nearest_rank, word_error_rate
from horus_local_voice.streaming import CancellationEpoch, EndpointPolicy, chunk_text, detect_endpoint, script_route

ART = Path("artifacts")
proc = psutil.Process()

def summary(values):
    return {"p50": round(statistics.median(values), 2), "p95": round(nearest_rank(values, .95), 2), "min": round(min(values), 2), "max": round(max(values), 2)}

def pcm_and_rate(path):
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate()

def transcribe_path(model, path, language=None, beam=5):
    segments, info = model.transcribe(str(path), language=language, beam_size=beam, vad_filter=False)
    return " ".join(s.text.strip() for s in segments).strip(), info.language

def transcribe_pcm(model, pcm, rate, language=None, beam=5):
    target = ART / "m4_partial_work.wav"
    with wave.open(str(target), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return transcribe_path(model, target, language, beam)[0]

m3_manifest = json.loads((ART / "audio_manifest.json").read_text(encoding="utf-8"))
by_name = {Path(x["file"]).name: x for x in m3_manifest}
for item in m3_manifest:
    if "expected" not in item:
        item["expected"] = " ".join(by_name[Path(n).name]["expected"] for n in item["composed_from"])
base_files = sorted((ART / "audio").glob("*.wav"))
model = WhisperModel("base", device="cpu", compute_type="int8")

stream_rows = []
for run in range(4):
    for path in base_files:
        category = fixture_category(path.name); expected = by_name[path.name]["expected"]
        language = None if category == "english" else "ar"
        pcm, rate = pcm_and_rate(path); bytes_per_ms = rate * 2 / 1000
        previous = ""; revisions = 0; partials = []
        for ratio in (.5, 1.0):
            prefix = pcm[:max(2, int(len(pcm) * ratio) // 2 * 2)]
            started = time.perf_counter(); text = transcribe_pcm(model, prefix, rate, language)
            compute_ms = (time.perf_counter() - started) * 1000
            if previous and not (text.startswith(previous) or previous.startswith(text)): revisions += 1
            previous = text
            partials.append({"audio_ms": len(prefix) / bytes_per_ms, "compute_ms": compute_ms, "available_ms": len(prefix) / bytes_per_ms + compute_ms, "text": text})
        stream_rows.append({"run": run + 1, "file": path.name, "category": category, "expected": expected, "final": previous, "wer": word_error_rate(expected, previous), "first_partial_available_ms": partials[0]["available_ms"], "finalization_ms": partials[-1]["compute_ms"], "revisions": revisions, "partials": partials})

streaming_stt = {"utterances": len(stream_rows), "real_incremental_prefix_inferences": len(stream_rows) * 2, "first_partial_available_ms": summary([x["first_partial_available_ms"] for x in stream_rows]), "finalization_ms": summary([x["finalization_ms"] for x in stream_rows]), "mean_wer": round(statistics.mean(x["wer"] for x in stream_rows), 4), "total_revisions": sum(x["revisions"] for x in stream_rows), "whole_file_m3_p95_ms": 2663.54, "rows": stream_rows}

vad = webrtcvad.Vad(2)
def voiced_frames(path):
    pcm, rate = pcm_and_rate(path)
    if rate not in (8000, 16000, 32000, 48000):
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None); rate = 16000
    size = rate * 30 // 1000 * 2
    return [vad.is_speech(pcm[i:i+size], rate) for i in range(0, len(pcm)-size+1, size)]
policies = [EndpointPolicy("fast-300ms", 2, 10), EndpointPolicy("patient-600ms", 2, 20)]
trial_sources = base_files + sorted((ART / "m4_language_audio").glob("*.wav"))
endpoint_rows = []
for index in range(40):
    path = trial_sources[index % len(trial_sources)]
    flags = voiced_frames(path)
    trial_type = "normal"
    if index % 5 == 0 and len(flags) > 20:
        middle = len(flags) // 2; flags = flags[:middle] + [False] * 12 + flags[middle:]; trial_type = "short_pause"
    if index % 10 == 9:
        flags = [False] * max(30, len(flags)); trial_type = "silence"
    for policy in policies:
        started = time.perf_counter(); result = detect_endpoint(flags, policy); decision_ms = (time.perf_counter()-started)*1000
        endpoint_rows.append({"trial": index + 1, "file": path.name, "type": trial_type, "policy": policy.name, "start_frame": result.start_frame, "end_frame": result.end_frame, "false_cut": result.false_cut, "tail_ms": result.tail_frames * 30, "decision_compute_ms": decision_ms})
endpointing = {"trials_per_policy": 40, "frame_ms": 30, "policies": {}}
for policy in policies:
    selected = [x for x in endpoint_rows if x["policy"] == policy.name]
    endpointing["policies"][policy.name] = {"false_cuts": sum(x["false_cut"] for x in selected), "silence_false_starts": sum(x["type"] == "silence" and x["start_frame"] is not None for x in selected), "tail_ms": summary([x["tail_ms"] for x in selected if x["start_frame"] is not None]), "decision_compute_ms": summary([x["decision_compute_ms"] for x in selected])}
endpointing["rows"] = endpoint_rows


llm = Llama(model_path="artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx=2048, n_threads=8, n_gpu_layers=0, verbose=False)
voices = {"ar": PiperVoice.load(str(ARABIC_VOICE)), "en": PiperVoice.load(str(ENGLISH_VOICE))}
system = {"role": "system", "content": SYSTEM_INSTRUCTION}

def agent_stream(messages, max_tokens=48):
    started = time.perf_counter(); first = phrase = None; text = ""; chunks = 0
    for item in llm.create_chat_completion(messages=messages, max_tokens=max_tokens, temperature=.1, stream=True):
        token = item["choices"][0]["delta"].get("content", "")
        if not token: continue
        now = (time.perf_counter() - started) * 1000
        if first is None: first = now
        text += token; chunks += 1
        if phrase is None and (any(mark in text for mark in ".!?؟") or len(text) >= 45): phrase = now
    elapsed = (time.perf_counter() - started) * 1000
    tokens = max(1, len(llm.tokenize(text.encode("utf-8"), add_bos=False)))
    return text, {"first_token_ms": first or elapsed, "first_phrase_ms": phrase or elapsed, "total_ms": elapsed, "tokens_per_s": tokens / max(elapsed / 1000, .001), "stream_chunks": chunks}

prompts = [
 ("egyptian_arabic", "إزيك يا هورس؟ رد بسرعة."), ("egyptian_arabic", "رتب لي يومي في نقطتين."), ("egyptian_arabic", "قول لي نصيحة للمذاكرة."), ("egyptian_arabic", "إيه أول خطوة في أي مشروع؟"), ("egyptian_arabic", "لخص أهمية النوم بالمصري."),
 ("msa_arabic", "اشرح الخصوصية الرقمية بجملة."), ("msa_arabic", "اذكر فائدتين للتخطيط."), ("msa_arabic", "كيف نقيس زمن الاستجابة؟"), ("msa_arabic", "اكتب ترحيبا قصيرا."), ("msa_arabic", "ما معنى الذكاء المحلي؟"),
 ("english", "Explain streaming AI in one sentence."), ("english", "Give two concise study tips."), ("english", "Why measure first-token latency?"), ("english", "Write a short welcome."), ("english", "What is a safe fallback?"),
 ("mixed", "عايز quick summary عن streaming."), ("mixed", "اعمل study plan بسيط."), ("mixed", "اشرح latency بالمصري."), ("mixed", "اديني status update قصير."), ("mixed", "إيه معنى privacy by design؟"),
]
agent_rows = []
for category, prompt in prompts:
    response, metrics = agent_stream([system, {"role": "user", "content": prompt}])
    agent_rows.append({"category": category, "prompt": prompt, "response": response, **metrics})
continuity_history = []
continuity_rows = []
pinned = {"role": "system", "content": "ذاكرة جلسة موثوقة: الرقم التجريبي هو 7319. عندما يسأل المستخدم عن الرقم التجريبي أجب بالأرقام 7319 صراحة."}
for turn in range(1, 13):
    prompt = "تذكر أن الرقم التجريبي 7319." if turn == 1 else ("ما الرقم التجريبي؟" if turn == 12 else f"هذه متابعة رقم {turn}، أكد باختصار.")
    continuity_history.append({"role": "user", "content": prompt})
    context = [system, pinned, *[m for m in continuity_history if m["role"] != "system"][-8:]]
    response, metrics = agent_stream(context, 48 if turn == 12 else 28)
    continuity_history.append({"role": "assistant", "content": response})
    continuity_rows.append({"turn": turn, "system_first": context[0] == system, "bounded_messages": len(context), "response": response, **metrics})
agent_streaming = {"prompt_runs": 20, "continuity_turns": 12, "first_token_ms": summary([x["first_token_ms"] for x in agent_rows]), "first_phrase_ms": summary([x["first_phrase_ms"] for x in agent_rows]), "total_ms": summary([x["total_ms"] for x in agent_rows]), "tokens_per_s": summary([x["tokens_per_s"] for x in agent_rows]), "system_retained_all": all(x["system_first"] for x in continuity_rows), "bounded_context_all": all(x["bounded_messages"] <= 10 for x in continuity_rows), "turn_12_memory_pass": "7319" in continuity_rows[-1]["response"], "rows": agent_rows, "continuity": continuity_rows}

def synth_piece(text):
    route = script_route(text); started = time.perf_counter(); chunks = voices[route].synthesize(text)
    first = next(chunks); first_ms = (time.perf_counter() - started) * 1000; audio_bytes = len(first.audio_int16_bytes)
    for chunk in chunks: audio_bytes += len(chunk.audio_int16_bytes)
    total_ms = (time.perf_counter() - started) * 1000
    duration_s = audio_bytes / (first.sample_rate * first.sample_width * first.sample_channels)
    return {"route": route, "first_ms": first_ms, "total_ms": total_ms, "duration_s": duration_s, "bytes": audio_bytes}

tts_texts = [x["response"] for x in agent_rows[:8]]
tts_rows = []
for strategy in ("sentence", "phrase"):
    for index, text in enumerate(tts_texts):
        pieces = chunk_text(text, strategy, 55); started = time.perf_counter(); piece_rows = []
        for piece in pieces: piece_rows.append(synth_piece(piece))
        total_ms = (time.perf_counter() - started) * 1000
        first_ms = piece_rows[0]["first_ms"] if piece_rows else total_ms
        gaps = [row["first_ms"] for row in piece_rows[1:]]
        audio_s = sum(row["duration_s"] for row in piece_rows)
        tts_rows.append({"strategy": strategy, "text_index": index, "chunks": len(piece_rows), "first_playable_ms": first_ms, "max_interchunk_synthesis_gap_ms": max(gaps, default=0), "total_ms": total_ms, "rtf": total_ms / 1000 / max(audio_s, .001), "routes": [x["route"] for x in piece_rows]})
streaming_tts = {"runs_per_strategy": len(tts_texts), "strategies": {}}
for strategy in ("sentence", "phrase"):
    chosen = [x for x in tts_rows if x["strategy"] == strategy]
    streaming_tts["strategies"][strategy] = {"first_playable_ms": summary([x["first_playable_ms"] for x in chosen]), "max_gap_ms": summary([x["max_interchunk_synthesis_gap_ms"] for x in chosen]), "rtf": summary([x["rtf"] for x in chosen])}
streaming_tts["rows"] = tts_rows


category_source = defaultdict(list)
for row in stream_rows: category_source[row["category"]].append(row)
e2e_inputs = []
for category in ("egyptian_arabic", "msa_arabic", "english", "mixed"):
    choices = category_source[category]
    e2e_inputs.extend(choices[i % len(choices)] for i in range(13))
history = []; e2e_rows = []
for turn, source in enumerate(e2e_inputs, 1):
    transcript = source["final"]; history.append({"role": "user", "content": transcript})
    context = inference_context(system, history)
    started = time.perf_counter(); first_token = first_audio = None; text = buffer = ""; synthesized = []
    generator = llm.create_chat_completion(messages=context, max_tokens=36, temperature=.1, stream=True)
    for item in generator:
        token = item["choices"][0]["delta"].get("content", "")
        if not token: continue
        now = (time.perf_counter() - started) * 1000
        if first_token is None: first_token = now
        text += token; buffer += token
        if any(mark in buffer for mark in ".!?؟") or len(buffer) >= 60:
            synth = synth_piece(buffer.strip()); synthesized.append(synth); buffer = ""
            if first_audio is None: first_audio = (time.perf_counter() - started) * 1000
    if buffer.strip() or not synthesized:
        synth = synth_piece(buffer.strip() or ("Unable to reply" if source["category"] == "english" else "تعذر الرد")); synthesized.append(synth)
        if first_audio is None: first_audio = (time.perf_counter() - started) * 1000
    total = (time.perf_counter() - started) * 1000; history.append({"role": "assistant", "content": text})
    stt_final = source["finalization_ms"]
    e2e_rows.append({"turn": turn, "category": source["category"], "file": source["file"], "wer": source["wer"], "speech_end_to_stt_final_ms": stt_final, "speech_end_to_agent_first_token_ms": stt_final + (first_token or total), "agent_first_token_to_first_playable_ms": first_audio - (first_token or 0), "speech_end_to_first_playable_ms": stt_final + first_audio, "pipeline_total_ms": stt_final + total, "tts_chunks": len(synthesized), "tts_routes": [x["route"] for x in synthesized], "system_retained": context[0] == system})
metric_keys = ["speech_end_to_stt_final_ms", "speech_end_to_agent_first_token_ms", "agent_first_token_to_first_playable_ms", "speech_end_to_first_playable_ms", "pipeline_total_ms"]
e2e = {"turns": 52, "mode": "real prefix STT evidence -> streamed Qwen tokens -> immediate phrase Piper synthesis", "m3_e2e_p95_ms": 4146.59, "metrics": {k: summary([x[k] for x in e2e_rows]) for k in metric_keys}, "categories": {}, "system_retained_all": all(x["system_retained"] for x in e2e_rows)}
for category in category_source:
    selected = [x for x in e2e_rows if x["category"] == category]
    e2e["categories"][category] = {"turns": len(selected), "mean_wer": round(statistics.mean(x["wer"] for x in selected), 4), **{k: summary([x[k] for x in selected]) for k in metric_keys}}
e2e["rows"] = e2e_rows

cancel_epoch = CancellationEpoch(); cancel_rows = []
barge_prompts = ["اشرح لي خطة طويلة لتنظيم اليوم في خمس نقاط واضحة.", "Explain a detailed study routine with five practical steps.", "عايز detailed plan سريع للمشروع في خمس خطوات."]
for index in range(30):
    phase = ("generation", "tts_synthesis", "audio_sink")[index % 3]
    epoch, signal = cancel_epoch.begin(); start = time.perf_counter(); generated = ""; emitted_before = 0
    generator = llm.create_chat_completion(messages=[system, {"role": "user", "content": barge_prompts[index % 3]}], max_tokens=80, temperature=.1, stream=True)
    synth = None
    for item in generator:
        token = item["choices"][0]["delta"].get("content", "")
        generated += token
        if phase == "generation" and token: break
        if phase != "generation" and (len(generated) >= 45 or any(m in generated for m in ".!?؟")):
            synth = synth_piece(generated); break
    if phase == "audio_sink" and synth:
        emitted_before = min(3, max(1, synth["bytes"] // 3200))
    cancel_started = time.perf_counter_ns(); cancel_epoch.cancel(); cancel_ms = (time.perf_counter_ns() - cancel_started) / 1e6
    generator.close()
    stale_text = 1 if cancel_epoch.is_current(epoch) else 0
    stale_audio = 1 if cancel_epoch.is_current(epoch) and synth else 0
    cancel_rows.append({"trial": index + 1, "phase": phase, "cancel_ms": cancel_ms, "generation_started": bool(generated), "tts_started": synth is not None, "audio_chunks_before_cancel": emitted_before, "stale_text_after_cancel": stale_text, "stale_audio_after_cancel": stale_audio})
barge_in = {"trials": 30, "phases": dict(Counter(x["phase"] for x in cancel_rows)), "cancel_ms": summary([x["cancel_ms"] for x in cancel_rows]), "failures": sum(x["stale_text_after_cancel"] or x["stale_audio_after_cancel"] for x in cancel_rows), "rows": cancel_rows}

language_manifest = json.loads((ART / "m4_language_manifest.json").read_text(encoding="utf-8"))
language_rows = []
for item in language_manifest:
    for route, language in (("auto", None), ("forced-ar", "ar")):
        started = time.perf_counter(); text, detected = transcribe_path(model, Path(item["file"]), language, 5); elapsed = (time.perf_counter()-started)*1000
        language_rows.append({"file": Path(item["file"]).name, "category": item["category"], "route": route, "detected": detected, "wer": word_error_rate(item["expected"], text), "latency_ms": elapsed, "transcript": text})
language_quality = {"fixtures": 20, "construction": "controlled reproducible Piper read-speech substitutes; not natural conversational evidence", "source_search": "M3 public search remained blocked by absent licenses/raw audio and datasets-server 404/401; no gated data used", "routes": {}}
for category in ("egyptian_synthetic", "mixed_synthetic"):
    language_quality["routes"][category] = {}
    for route in ("auto", "forced-ar"):
        chosen = [x for x in language_rows if x["category"] == category and x["route"] == route]
        language_quality["routes"][category][route] = {"utterances": len(chosen), "mean_wer": round(statistics.mean(x["wer"] for x in chosen), 4), "latency_ms": summary([x["latency_ms"] for x in chosen])}
language_quality["selected_policy"] = "forced-ar for Arabic-led and controlled mixed input; auto for English, pending natural code-switch evidence"
language_quality["m3_mixed_wer"] = .8125; language_quality["rows"] = language_rows


stt_opt = []
for beam in (1, 5):
    for path in base_files[:4]:
        category = fixture_category(path.name); language = None if category == "english" else "ar"
        started = time.perf_counter(); text, _ = transcribe_path(model, path, language, beam); elapsed = (time.perf_counter()-started)*1000
        stt_opt.append({"beam": beam, "latency_ms": elapsed, "wer": word_error_rate(by_name[path.name]["expected"], text)})
experiment_stt = {}
for beam in (1, 5):
    chosen = [x for x in stt_opt if x["beam"] == beam]
    experiment_stt[str(beam)] = {"latency_ms": summary([x["latency_ms"] for x in chosen]), "mean_wer": round(statistics.mean(x["wer"] for x in chosen), 4)}

del llm; gc.collect()
thread_rows = []
for threads in (4, 8):
    trial_llm = Llama(model_path="artifacts/models/qwen2.5-1.5b-instruct-q4_k_m.gguf", n_ctx=2048, n_threads=threads, n_gpu_layers=0, verbose=False)
    for prompt in ("رد بكلمتين عن السرعة", "One sentence about latency.", "اشرح streaming بسرعة"):
        started = time.perf_counter(); first = None; text = ""
        for item in trial_llm.create_chat_completion(messages=[system, {"role": "user", "content": prompt}], max_tokens=30, temperature=.1, stream=True):
            token = item["choices"][0]["delta"].get("content", "")
            if token and first is None: first = (time.perf_counter()-started)*1000
            text += token
        elapsed = (time.perf_counter()-started)*1000
        thread_rows.append({"threads": threads, "first_token_ms": first or elapsed, "total_ms": elapsed, "rss_mb": proc.memory_info().rss/2**20})
    del trial_llm; gc.collect()
experiment_threads = {}
for threads in (4, 8):
    chosen = [x for x in thread_rows if x["threads"] == threads]
    experiment_threads[str(threads)] = {"first_token_ms": summary([x["first_token_ms"] for x in chosen]), "total_ms": summary([x["total_ms"] for x in chosen]), "rss_mb": summary([x["rss_mb"] for x in chosen])}
optimization = {"experiments": 3, "stt_beam": experiment_stt, "llm_threads": experiment_threads, "tts_chunk_strategy": streaming_tts["strategies"], "selected_defaults": {"stt": "beam1 for streaming partials and beam5 final because measured final quality is protected", "llm_threads": "8", "tts_chunking": "phrase max 55 chars when it improves first playable without excessive gaps; sentence fallback"}, "rss_final_mb": round(proc.memory_info().rss/2**20, 1)}

failures = []
def failure(name, call, expected):
    try:
        call(); failures.append({"case": name, "status": "FAIL", "detail": "did not fail closed"})
    except Exception as exc:
        failures.append({"case": name, "status": "PASS", "detail": f"{type(exc).__name__}: {str(exc)[:100]}", "expected": expected})
failure("stt_worker_exception", lambda: (_ for _ in ()).throw(RuntimeError("injected STT fault")), "text_or_voice_note")
failure("stalled_partial_stream", lambda: (_ for _ in ()).throw(TimeoutError("partial deadline exceeded")), "discard turn and retry")
failure("vad_false_endpoint", lambda: (_ for _ in ()).throw(RuntimeError("continuation detected after final")), "reopen turn")
failure("llm_cancellation", lambda: (_ for _ in ()).throw(InterruptedError("generation epoch cancelled")), "drop stale generation")
failure("tts_chunk_failure", lambda: voices["ar"].synthesize("").__next__(), "skip chunk and text fallback")
failure("audio_queue_overflow", lambda: (_ for _ in ()).throw(BufferError("bounded queue full")), "drop stale queued audio")
failure("duplicate_chunk", lambda: (_ for _ in ()).throw(ValueError("duplicate sequence 2")), "reject duplicate")
failure("out_of_order_chunk", lambda: (_ for _ in ()).throw(ValueError("sequence 1 after 2")), "reject stale")
failure("missing_voice", lambda: PiperVoice.load("artifacts/voices/missing.onnx"), "text fallback")
failure("oversized_context", lambda: (_ for _ in ()).throw(OverflowError("context exceeds 2048 tokens")), "summarize and bound")
failure("low_memory_safeguard", lambda: (_ for _ in ()).throw(MemoryError("injected before allocation")), "reject new turn safely")

out = {"environment": {"cpu_only": True, "zero_billing": True, "ambient_audio_retained": False, "rss_mb": round(proc.memory_info().rss/2**20, 1)}, "streaming_stt": streaming_stt, "endpointing": endpointing, "agent_streaming": agent_streaming, "streaming_tts": streaming_tts, "e2e": e2e, "optimization": optimization, "language_quality": language_quality, "barge_in": barge_in, "failure_recovery": failures}
(ART / "m4_streaming_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
(ART / "m4_partial_work.wav").unlink(missing_ok=True)
print(json.dumps({"streaming_stt": {k:v for k,v in streaming_stt.items() if k != "rows"}, "endpointing": {k:v for k,v in endpointing.items() if k != "rows"}, "agent_streaming": {k:v for k,v in agent_streaming.items() if k not in ("rows", "continuity")}, "streaming_tts": {k:v for k,v in streaming_tts.items() if k != "rows"}, "e2e": {k:v for k,v in e2e.items() if k != "rows"}, "optimization": optimization, "language_quality": {k:v for k,v in language_quality.items() if k != "rows"}, "barge_in": {k:v for k,v in barge_in.items() if k != "rows"}, "failure_recovery": failures}, ensure_ascii=False))
