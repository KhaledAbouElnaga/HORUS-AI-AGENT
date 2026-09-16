# Explicit routing and context policies used by the Milestone 3 benchmark.
from __future__ import annotations

import re
from pathlib import Path

SYSTEM_INSTRUCTION = "أنت هورس. رد بجملة قصيرة بنفس لغة المستخدم ولا تستخدم أدوات."
ARABIC_VOICE = Path("artifacts/voices/ar_JO-kareem-medium.onnx")
ENGLISH_VOICE = Path("artifacts/voices/en_US-lessac-medium.onnx")


def fixture_category(filename: str) -> str:
    if filename.startswith("egyptian_arabic_"):
        return "egyptian_arabic"
    if filename.startswith("arabic_msa_"):
        return "msa_arabic"
    if filename.startswith("english_"):
        return "english"
    if filename == "mixed_ar_en.wav":
        return "mixed"
    raise ValueError(f"unknown fixture category: {filename}")


def stt_language_for(category: str) -> str | None:
    return None if category == "english" else "ar"


def tts_voice_for(category: str, reply: str) -> Path:
    if category == "english":
        return ENGLISH_VOICE
    if category != "mixed":
        return ARABIC_VOICE
    arabic = len(re.findall(r"[؀-ۿ]", reply))
    latin = len(re.findall(r"[A-Za-z]", reply))
    return ENGLISH_VOICE if latin > arabic else ARABIC_VOICE


def inference_context(system: dict, history: list[dict], recent_messages: int = 8) -> list[dict]:
    non_system = [message for message in history if message.get("role") != "system"]
    return [system, *non_system[-recent_messages:]]
