import wave

from horus_local_voice.integration import VoiceRuntimePipeline
from horus_local_voice.runtime_adapter import VoiceRuntimeAdapter
from horus_local_voice.streaming import IncrementalTranscriber


class Runtime:
    def resume_session(self, session_id):
        self.sessions = getattr(self, "sessions", [])
        self.sessions.append(session_id)

    def stream_turn(self, session_id, text, cancel):
        yield f"reply for {session_id}: "
        yield text

    def search_memory(self, session_id, query):
        return []

    def write_memory(self, session_id, fact):
        return {"session_id": session_id, "fact": fact}

    def invoke_tool(self, session_id, category, arguments):
        return {"category": category, "arguments": arguments}

    def cancel(self, session_id):
        pass


def test_wav_pipeline_reaches_runtime_and_incremental_audio(tmp_path):
    path = tmp_path / "turn.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x01\x00" * 16000)

    adapter = VoiceRuntimeAdapter(Runtime())
    adapter.open_session("s1")
    transcriber = IncrementalTranscriber(lambda pcm: "hello")
    audio = []
    pipeline = VoiceRuntimePipeline(adapter, transcriber, lambda text: text, audio.append)
    turn = pipeline.run_wav_turn("s1", path)

    assert turn.transcript == "hello"
    assert turn.response == "reply for s1: hello"
    assert turn.audio_chunks == 1
    assert audio == ["reply for s1: hello"]
    assert turn.metrics.final_to_first_token_ms is not None
    assert turn.metrics.first_token_to_first_audio_ms is not None
