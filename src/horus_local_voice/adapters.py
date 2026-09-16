"""Replaceable adapter boundaries for the local voice prototype."""
from typing import Protocol


class VAD(Protocol):
    def is_speech(self, frame: bytes) -> bool: ...


class STT(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


class AgentRuntime(Protocol):
    def respond(self, text: str, context: list[str]) -> str: ...


class TTS(Protocol):
    def stream(self, text: str): ...


class AudioIO(Protocol):
    def read(self): ...
    def write(self, chunk: bytes) -> None: ...
