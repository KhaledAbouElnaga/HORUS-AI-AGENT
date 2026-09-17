import json
import wave
from pathlib import Path
from piper import PiperVoice

OUT = Path("artifacts/m4_language_audio")
OUT.mkdir(parents=True, exist_ok=True)
ar = PiperVoice.load("artifacts/voices/ar_JO-kareem-medium.onnx")
en = PiperVoice.load("artifacts/voices/en_US-lessac-medium.onnx")
egyptian = [
    "إزيك يا هورس عامل إيه النهارده", "ممكن ترتب لي مواعيدي بسرعة", "عايز أعرف الجو هيبقى عامل إزاي",
    "فكرني أكلم ماما بعد الشغل", "قول لي أهم حاجة أبدأ بيها دلوقتي", "أنا محتاج خطة مذاكرة بسيطة",
    "خلي الرد قصير ومن غير تفاصيل كتير", "ممكن تلخص لي الكلام ده بالمصري", "إيه أحسن طريقة أنظم بيها يومي",
    "اكتب لي رسالة ترحيب خفيفة",
]
mixed = [
    ("عايز", "quick summary", "عن الاجتماع"), ("اعمل لي", "to do list", "للنهارده"),
    ("اشرح لي معنى", "machine learning", "ببساطة"), ("محتاج", "study plan", "للأسبوع الجاي"),
    ("قول لي", "the next step", "في المشروع"), ("راجع", "email draft", "وخليه مختصر"),
    ("إيه الفرق بين", "privacy and security", "بالمصري"), ("اعمل", "backup", "للملفات المهمة"),
    ("شغل", "focus mode", "لمدة ساعة"), ("اديني", "status update", "عن المهمة"),
]

def synth(voice, text):
    chunks = voice.synthesize(text)
    first = next(chunks); data = bytearray(first.audio_int16_bytes)
    for chunk in chunks: data.extend(chunk.audio_int16_bytes)
    return first, bytes(data)

rows = []
for index, text in enumerate(egyptian, 1):
    first, data = synth(ar, text); path = OUT / f"egyptian_synthetic_{index:02}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(first.sample_channels); w.setsampwidth(first.sample_width); w.setframerate(first.sample_rate); w.writeframes(data)
    rows.append({"file": str(path), "category": "egyptian_synthetic", "expected": text, "construction": "Piper Arabic read-speech substitute"})
for index, (left, english, right) in enumerate(mixed, 1):
    parts = [synth(ar, left), synth(en, english), synth(ar, right)]
    first = parts[0][0]; gap = b"\x00\x00" * int(first.sample_rate * 0.08)
    data = gap.join(part[1] for part in parts); path = OUT / f"mixed_synthetic_{index:02}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(first.sample_channels); w.setsampwidth(first.sample_width); w.setframerate(first.sample_rate); w.writeframes(data)
    rows.append({"file": str(path), "category": "mixed_synthetic", "expected": f"{left} {english} {right}", "construction": "concatenated Arabic/English Piper read-speech substitute"})
Path("artifacts/m4_language_manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"fixtures": len(rows), "egyptian": 10, "mixed": 10, "ambient_audio_retained": False}, ensure_ascii=False))
