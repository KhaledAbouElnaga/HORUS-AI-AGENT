"""Run offline faster-whisper against the downloaded WAV fixtures."""
import json
import time
from pathlib import Path
from faster_whisper import WhisperModel

ROOT = Path(__file__).parents[1]
manifest = json.loads((ROOT / 'artifacts/audio_manifest.json').read_text(encoding='utf-8'))
model_size = 'tiny'
load_start = time.perf_counter()
model = WhisperModel(model_size, device='cpu', compute_type='int8')
load_ms = (time.perf_counter() - load_start) * 1000
results = []
for item in manifest[:-1]:
    path = ROOT / item['file']
    start = time.perf_counter()
    segments, info = model.transcribe(str(path), beam_size=1, vad_filter=False)
    text = ' '.join(s.text.strip() for s in segments).strip()
    results.append({**item, 'observed': text, 'latency_ms': round((time.perf_counter()-start)*1000, 2), 'duration_s': info.duration, 'language': info.language})
output = {'model': model_size, 'device': 'cpu', 'compute_type': 'int8', 'load_ms': round(load_ms, 2), 'results': results}
(ROOT / 'artifacts/stt_results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'model': model_size, 'load_ms': round(load_ms, 2), 'clips': len(results), 'output': 'artifacts/stt_results.json'}, ensure_ascii=False))
