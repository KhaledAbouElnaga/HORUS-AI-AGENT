import threading
import time
import wave
from pathlib import Path

import pytest

from horus_local_voice.real_audio import inspect_pcm_wav, nearest_rank, stream_until_cancelled, word_error_rate


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
