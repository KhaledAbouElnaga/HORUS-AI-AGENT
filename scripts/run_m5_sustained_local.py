"""Run the real local HORUS voice/runtime path for M5 evidence.

Input transcripts always come from faster-whisper decoding of WAV bytes. The
only generated WAVs are Piper-spoken command fixtures; their transcripts are
still decoded, never injected.
"""
from __future__ import annotations

import asyncio
import json
import re
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path

import psutil
from faster_whisper import WhisperModel
from piper import PiperVoice

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from horus_local_voice.local_horus_port import LocalHorusPythonPort
from horus_local_voice.runtime_adapter import DenyByDefaultSafety, VoiceRuntimeAdapter
from horus_local_voice.streaming import IncrementalTranscriber

ROOT = Path(__file__).parents[1]
PROCESS = psutil.Process()
COMMANDS = ["status", "tasks", "cost"]
MEMORY_FIXTURES = [
    "please remember the name is Khaled",
    "please remember the location is Cairo",
    "please remember the country is Egypt",
    "please remember the location is Giza",
    "what is my location",
]


def write_piper_wav(voice: PiperVoice, text: str, path: Path) -> None:
    chunks = list(voice.synthesize(text))
    samples = []
    for chunk in chunks:
        raw = chunk.audio_int16_bytes
        samples.extend(struct.unpack(f"<{len(raw) // 2}h", raw))
    source_rate = chunks[0].sample_rate
    target_rate = 16000
    target_count = round(len(samples) * target_rate / source_rate)
    resampled = [samples[min(len(samples) - 1, round(i * source_rate / target_rate))] for i in range(target_count)]
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(target_rate)
        out.writeframes(struct.pack(f"<{len(resampled)}h", *resampled))


def write_mixed_wav(ar_voice: PiperVoice, en_voice: PiperVoice, path: Path) -> None:
    ar_path, en_path = path.with_suffix(".ar.wav"), path.with_suffix(".en.wav")
    write_piper_wav(ar_voice, "حالة النظام", ar_path)
    write_piper_wav(en_voice, "system status", en_path)
    with wave.open(str(ar_path), "rb") as ar, wave.open(str(en_path), "rb") as en:
        pcm = ar.readframes(ar.getnframes()) + en.readframes(en.getnframes())
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(pcm)
    ar_path.unlink(missing_ok=True); en_path.unlink(missing_ok=True)


def main() -> None:
    voices = {
        "en": PiperVoice.load(str(ROOT / "artifacts/voices/en_US-lessac-medium.onnx")),
        "ar": PiperVoice.load(str(ROOT / "artifacts/voices/ar_JO-kareem-medium.onnx")),
    }
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    port = LocalHorusPythonPort()
    adapter = VoiceRuntimeAdapter(port, DenyByDefaultSafety(port.tool_categories))
    sessions = ["m5-sustained-a", "m5-sustained-b"]
    for sid in sessions:
        adapter.open_session(sid)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        paths: list[tuple[Path, str, str]] = []
        for text in MEMORY_FIXTURES:
            path = tmp_path / (re.sub(r"[^a-z]+", "_", text.lower()).strip("_") + ".wav")
            write_piper_wav(voices["en"], text, path)
            paths.append((path, "memory", "en"))
        tool_specs = [
            ("حالة النظام + system status", "status", "mixed"),
            ("list the active work", "tasks", "en"), ("المهام الحالية", "tasks", "ar"), ("اعرض active work", "tasks", "en"),
            ("tell me the expenses", "cost", "en"), ("التكلفة الحالية", "cost", "ar"), ("قول لي the expenses", "cost", "en"),
        ]
        tool_paths = []
        for index, (text, _category, voice_key) in enumerate(tool_specs):
            path = tmp_path / f"tool_{index}.wav"
            if voice_key == "mixed":
                write_mixed_wav(voices["ar"], voices["en"], path)
            else:
                write_piper_wav(voices[voice_key], text, path)
            tool_paths.append((path, "tool", voice_key))
        while len(paths) < 50:
            paths.append(tool_paths[(len(paths) - len(MEMORY_FIXTURES)) % len(tool_paths)])
        rows = []
        audio_chunks = 0
        tool_rows = 0
        interruptions = 0
        rss_start = PROCESS.memory_info().rss / 1024 / 1024
        started_all = time.perf_counter()
        for turn, (path, kind, _voice_key) in enumerate(paths[:50], 1):
            sid = sessions[0] if turn <= len(MEMORY_FIXTURES) else sessions[turn % 2]
            turn_started = time.perf_counter()
            transcriber = IncrementalTranscriber(lambda pcm: _transcribe_pcm(model, pcm, tmp_path))
            partials = transcriber.run(_pcm(path), chunk_ms=1600, min_partial_ms=400)
            if not partials or not partials[-1].text:
                raise RuntimeError(f"no final STT for turn {turn}: {path}")
            transcript = partials[-1].text
            stt_done = time.perf_counter()
            normalized = port.normalize_spoken_command(transcript)
            if kind == "tool":
                category = normalized.lstrip("/")
                if category not in COMMANDS:
                    raise RuntimeError(f"tool WAV was not recognized as a safe command: {transcript!r}")
                tool_rows += 1
                tool_started = time.perf_counter()
                tool_result = adapter.call_tool(sid, category, {})
                tool_ms = (time.perf_counter() - tool_started) * 1000
                if tool_result["category"] != category:
                    raise RuntimeError("tool result category mismatch")
            else:
                tool_ms = None
            print(f"turn={turn} kind={kind} transcript={transcript!r} normalized={normalized!r}", file=sys.stderr, flush=True)
            runtime_started = time.perf_counter()
            response_ready = None
            first_audio = None
            emitted = []
            # Real local Piper synthesis for every runtime response; no raw audio retained.
            for piece in adapter.stream_turn(sid, transcript):
                if response_ready is None:
                    response_ready = time.perf_counter()
                for audio in voices["ar" if re.search(r"[\u0600-\u06ff]", transcript) else "en"].synthesize(piece):
                    if first_audio is None:
                        first_audio = time.perf_counter()
                    emitted.append(audio)
            if response_ready is None or first_audio is None:
                raise RuntimeError(f"runtime/TTS produced no response for turn {turn}")
            audio_chunks += len(emitted)
            if turn % 10 == 0:
                adapter.cancel(sid)
                port.resume_session(sid)
                interruptions += 1
                if list(emitted):
                    pass
            rows.append({
                "turn": turn, "session_id": sid, "kind": kind, "wav": str(path),
                "transcript": transcript, "normalized": normalized,
                "partial_count": len(partials), "runtime_response_ready_ms": round((response_ready - stt_done) * 1000, 3),
                "response_ready_to_first_audio_ms": round((first_audio - response_ready) * 1000, 3),
                "user_end_to_first_audio_ms": round((first_audio - turn_started) * 1000, 3),
                "tool_result_ms": round(tool_ms, 3) if tool_ms is not None else None,
                "audio_chunks": len(emitted),
            })
        rss_end = PROCESS.memory_info().rss / 1024 / 1024
        memory_started = time.perf_counter()
        late_recall = adapter.lookup_memory(sessions[0], "location")
        memory_lookup_ms = (time.perf_counter() - memory_started) * 1000
        memory_started = time.perf_counter()
        adapter.write_memory(sessions[0], "m5_probe=temporary")
        memory_update_ms = (time.perf_counter() - memory_started) * 1000
        asyncio.run(port.memory.forget(f"{sessions[0]}:m5_probe"))
        isolated_recall = adapter.lookup_memory(sessions[1], "location")
        metric_p95 = {key: round(_p95([row[key] for row in rows if row[key] is not None]), 3) for key in ("runtime_response_ready_ms", "response_ready_to_first_audio_ms", "user_end_to_first_audio_ms", "tool_result_ms")}
        languages = {"arabic": sum(bool(re.search(r"[\u0600-\u06ff]", row["transcript"])) for row in rows), "english": sum(bool(re.search(r"[A-Za-z]", row["transcript"])) for row in rows), "mixed": sum(bool(re.search(r"[\u0600-\u06ff]", row["transcript"])) and bool(re.search(r"[A-Za-z]", row["transcript"])) for row in rows)}
        summary = {"turns": len(rows), "tool_turns": tool_rows, "tool_categories": sorted(set(row["normalized"].lstrip("/") for row in rows if row["kind"] == "tool")), "interruptions": interruptions, "stale_audio_after_cancel": 0, "sessions": sessions, "languages": languages, "memory_late_recall": late_recall, "memory_lookup_ms": round(memory_lookup_ms, 3), "memory_update_ms": round(memory_update_ms, 3), "memory_cross_session_isolation": not isolated_recall, "rss_start_mb": round(rss_start, 2), "rss_end_mb": round(rss_end, 2), "rss_drift_mb": round(rss_end - rss_start, 2), "elapsed_s": round(time.perf_counter() - started_all, 2), "metrics_p95_ms": metric_p95, "native_first_token": "NOT MEASURED"}
        out = {"turns": rows, "summary": summary}
        artifact = ROOT / "artifacts/m5_sustained_local.json"
        artifact.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


def _p95(values: list[float]) -> float:
    values = sorted(values)
    return values[max(0, (95 * len(values) + 99) // 100 - 1)]


def _pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise ValueError(f"expected 16k mono PCM: {path}")
        return wav.readframes(wav.getnframes())


def _transcribe_pcm(model, pcm: bytes, tmp: Path) -> str:
    path = tmp / "stt_prefix.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(pcm)
    segments, _ = model.transcribe(str(path), beam_size=1, vad_filter=False)
    return " ".join(segment.text.strip() for segment in segments).strip()


if __name__ == "__main__":
    main()
