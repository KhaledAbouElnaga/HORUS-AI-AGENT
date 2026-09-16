import threading
import time
import wave
import random
import struct
from pathlib import Path

import pytest

from horus_local_voice.real_audio import execute_bounded_adapter, inspect_pcm_wav, nearest_rank, stream_until_cancelled, webrtc_vad_wav, word_error_rate
from horus_local_voice.m3_policy import ARABIC_VOICE, ENGLISH_VOICE, inference_context, stt_language_for, tts_voice_for


def make_wav(path: Path, samples: bytes = b"\x00\x10" * 1600) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(samples)


def test_pcm_wav_ingestion_and_energy_vad(tmp_path):
    path = tmp_path / "speech.wav"; make_wav(path)
    facts = inspect_pcm_wav(path)
    assert facts["speech_detected"] and facts["duration_s"] == pytest.approx(0.1)


def test_corrupt_audio_fails_closed(tmp_path):
    path = tmp_path / "bad.wav"; path.write_bytes(b"not a wav")
    with pytest.raises(ValueError, match="corrupted WAV"):
        inspect_pcm_wav(path)


def test_missing_audio_fails_closed(tmp_path):
    with pytest.raises((FileNotFoundError, ValueError)):
        inspect_pcm_wav(tmp_path / "missing.wav")


def test_word_error_rate_normalizes_case_punctuation_and_arabic_diacritics():
    assert word_error_rate("Hello, WORLD!", "hello world") == 0
    assert word_error_rate("أَهْلًا بك", "اهلا بك") == 0
    assert word_error_rate("one two", "one three") == 0.5


def test_nearest_rank_p95():
    assert nearest_rank(list(range(1, 21)), 0.95) == 19


def test_active_stream_cancels_and_never_resumes(tmp_path):
    path = tmp_path / "long.wav"; make_wav(path, b"\x00\x10" * 16000)
    cancel = threading.Event(); timer = threading.Timer(0.04, cancel.set); timer.start()
    started = time.perf_counter_ns(); result = stream_until_cancelled(path, cancel, chunk_ms=5); timer.join()
    assert result["cancelled"] is True
    assert result["chunks"] < 200
    assert (result["detected_at_ns"] - started) / 1e6 < 100


def test_webrtc_vad_speech_silence_and_low_noise(tmp_path):
    speech = webrtc_vad_wav(Path("artifacts/audio/english_01.wav"))
    silence = tmp_path / "silence.wav"
    low_noise = tmp_path / "low_noise.wav"
    make_wav(silence, b"\x00\x00" * 16000)
    random.seed(7)
    samples = [random.randint(-8, 8) for _ in range(16000)]
    make_wav(low_noise, struct.pack("<" + "h" * len(samples), *samples))
    assert speech.speech_detected
    assert not webrtc_vad_wav(silence).speech_detected
    assert not webrtc_vad_wav(low_noise).speech_detected


def test_real_adapter_boundary_fails_closed_on_stt_error():
    result = execute_bounded_adapter(lambda: (_ for _ in ()).throw(RuntimeError("stt failed")), 0.2)
    assert not result.ok and "stt failed" in result.error
    assert result.fallback == "text_or_voice_note"


def test_real_adapter_boundary_times_out_stt():
    result = execute_bounded_adapter(lambda: time.sleep(0.1), 0.01)
    assert not result.ok and result.timed_out


def test_real_adapter_boundary_fails_closed_on_tts_error():
    result = execute_bounded_adapter(lambda: (_ for _ in ()).throw(OSError("tts failed")), 0.2)
    assert not result.ok and "tts failed" in result.error


def test_system_instruction_survives_beyond_ten_turns():
    system = {"role": "system", "content": "non-negotiable instruction"}
    history = []
    for turn in range(12):
        history.extend((
            {"role": "user", "content": f"user-{turn}"},
            {"role": "assistant", "content": f"assistant-{turn}"},
        ))
    context = inference_context(system, history)
    assert context[0] == system
    assert len(context) == 9
    assert context[-1]["content"] == "assistant-11"


def test_m3_language_routes_are_explicit_and_fail_safe():
    assert stt_language_for("english") is None
    assert stt_language_for("egyptian_arabic") == "ar"
    assert stt_language_for("mixed") == "ar"
    assert tts_voice_for("english", "Hello") == ENGLISH_VOICE
    assert tts_voice_for("mixed", "ملخص سريع quick") == ARABIC_VOICE
    assert tts_voice_for("mixed", "Quick summary ملخص") == ENGLISH_VOICE
