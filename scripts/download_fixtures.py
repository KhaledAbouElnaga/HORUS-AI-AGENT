"""Download small, reproducible public FLEURS WAV fixtures (no auth)."""
import json
import sys
import urllib.parse
import urllib.request
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / 'artifacts' / 'audio'
OUT.mkdir(parents=True, exist_ok=True)


def rows(dataset, split, count, config='default'):
    q = urllib.parse.urlencode({'dataset': dataset, 'config': config, 'split': split})
    with urllib.request.urlopen('https://datasets-server.huggingface.co/first-rows?' + q, timeout=120) as r:
        return json.load(r)['rows'][:count]


def download(label, dataset, split, count, config='default'):
    manifest = []
    for i, item in enumerate(rows(dataset, split, count, config)):
        row = item['row']
        url = row['audio'][0]['src']
        target = OUT / f'{label}_{i+1:02d}.wav'
        with urllib.request.urlopen(url, timeout=120) as r:
            target.write_bytes(r.read())
        normalized = target.with_suffix('.normalized.wav')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(target), '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(normalized)], check=True)
        target.unlink()
        normalized.replace(target)
        manifest.append({'file': str(target.relative_to(ROOT)), 'expected': row.get('transcription', row.get('text', '')), 'dataset': dataset, 'split': split, 'config': config, 'row': item['row_idx'], 'language': row.get('language', 'English')})
    return manifest

manifest = download('egyptian_arabic', 'MohamedRashad/fleurs-ar-eg', 'test', 3)
manifest += download('arabic_msa', 'MohamedRashad/fleurs-ar-eg', 'test', 2)
manifest += download('english', 'hf-internal-testing/librispeech_asr_dummy', 'validation', 2, 'clean')
# A reproducible mixed-language fixture is a real Arabic clip followed by a real English clip.
from wave import open as wave_open
with wave_open(str(OUT / 'egyptian_arabic_01.wav'), 'rb') as a, wave_open(str(OUT / 'english_01.wav'), 'rb') as b:
    if a.getparams()[:3] != b.getparams()[:3]:
        raise RuntimeError('fixture formats differ')
    with wave_open(str(OUT / 'mixed_ar_en.wav'), 'wb') as out:
        out.setparams(a.getparams())
        out.writeframes(a.readframes(a.getnframes()))
        out.writeframes(b.readframes(b.getnframes()))
manifest.append({'file': 'artifacts/audio/mixed_ar_en.wav', 'composed_from': ['artifacts/audio/egyptian_arabic_01.wav', 'artifacts/audio/english_01.wav'], 'note': 'concatenated real clips; not a natural code-switch recording'})
(ROOT / 'artifacts' / 'audio_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'downloaded': len(manifest)-1, 'manifest': 'artifacts/audio_manifest.json'}, ensure_ascii=False))
