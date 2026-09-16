"""Milestone 3 repeated apples-to-apples faster-whisper benchmark."""
import json
import os
import statistics
import time
from pathlib import Path

import psutil
from faster_whisper import WhisperModel
from horus_local_voice.real_audio import nearest_rank, word_error_rate

manifest = json.loads(Path("artifacts/audio_manifest.json").read_text(encoding="utf-8"))
by_file = {Path(x["file"]).as_posix(): x for x in manifest}
fixtures = []
for path in sorted(Path("artifacts/audio").glob("*.wav")):
    if path.name == "mixed_ar_en.wav":
        expected = manifest[0]["expected"] + " " + next(x["expected"] for x in manifest if "english" in x["file"])
        category = "mixed"
    else:
        expected = by_file[path.as_posix()]["expected"]
        category = path.stem.rsplit("_", 1)[0]
    fixtures.append({"path": path, "expected": expected, "category": category})
configs = [
    {"id": "tiny_auto_int8", "model": "tiny", "forced_ar": False, "beam": 1},
    {"id": "base_auto_int8", "model": "base", "forced_ar": False, "beam": 1},
    {"id": "base_ar_forced_beam5_int8", "model": "base", "forced_ar": True, "beam": 5},
]
all_results = []
proc = psutil.Process()
for cfg in configs:
    before = proc.memory_info().rss
    started = time.perf_counter(); model = WhisperModel(cfg["model"], device="cpu", compute_type="int8"); load_ms = (time.perf_counter() - started) * 1000
    warm = fixtures[0]; list(model.transcribe(str(warm["path"]), beam_size=cfg["beam"], language="ar" if cfg["forced_ar"] else None)[0])
    rows = []
    for repeat in range(3):
        for item in fixtures:
            language = "ar" if cfg["forced_ar"] and item["category"] != "english" else None
            started = time.perf_counter(); segments, info = model.transcribe(str(item["path"]), beam_size=cfg["beam"], language=language, vad_filter=False); observed = " ".join(x.text.strip() for x in segments).strip(); latency = (time.perf_counter() - started) * 1000
            rows.append({"repeat": repeat + 1, "file": item["path"].name, "category": item["category"], "observed": observed, "wer": word_error_rate(item["expected"], observed), "latency_ms": latency, "detected_language": info.language, "forced_language": language})
    lats = [x["latency_ms"] for x in rows]; wers = [x["wer"] for x in rows]
    categories = {cat: round(statistics.mean(x["wer"] for x in rows if x["category"] == cat), 4) for cat in sorted({x["category"] for x in rows})}
    cache = Path.home() / ".cache/huggingface/hub" / ("models--Systran--faster-whisper-" + cfg["model"])
    size = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file()) if cache.exists() else None
    all_results.append({"config": cfg, "load_ms": round(load_ms, 2), "model_cache_bytes": size, "rss_delta_mb": round((proc.memory_info().rss-before)/2**20, 1), "rss_mb": round(proc.memory_info().rss/2**20, 1), "mean_wer": round(statistics.mean(wers), 4), "category_wer": categories, "latency_p50_ms": round(statistics.median(lats), 2), "latency_p95_ms": round(nearest_rank(lats, .95), 2), "rows": rows})
    del model
out = {"runs_per_config": 3, "fixture_count": len(fixtures), "device": "CPU int8", "gpu_available_but_unused": "RTX 3050 4GB; CUDA runtime path not configured for CTranslate2", "results": all_results}
Path("artifacts/m3_stt_comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps([{k:v for k,v in x.items() if k != "rows"} for x in all_results], ensure_ascii=False))
