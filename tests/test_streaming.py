import threading

from horus_local_voice.streaming import CancellationEpoch, EndpointPolicy, IncrementalTranscriber, PipelinedResponder, StreamState, chunk_text, detect_endpoint, script_route


def test_incremental_transcriber_emits_partials_and_final():
    seen = []
    def transcribe(pcm):
        seen.append(len(pcm)); return f"heard-{len(pcm)}"
    rows = IncrementalTranscriber(transcribe).run(b"x" * 64000, chunk_ms=500)
    assert len(rows) == 4 and rows[-1].stable
    assert rows[-1].audio_ms == 2000 and seen == sorted(seen)
    assert rows[-1].revisions == 3


def test_endpoint_policies_detect_pause_tradeoff():
    frames = [False] * 3 + [True] * 10 + [False] * 8 + [True] * 8 + [False] * 20
    fast = detect_endpoint(frames, EndpointPolicy("fast", 2, 6))
    patient = detect_endpoint(frames, EndpointPolicy("patient", 2, 12))
    assert fast.false_cut and not patient.false_cut
    assert patient.tail_frames == 12


def test_endpoint_silence_has_no_turn():
    result = detect_endpoint([False] * 40, EndpointPolicy("x", 2, 8))
    assert result.start_frame is None and result.end_frame is None


def test_chunking_and_script_routes():
    assert chunk_text("One sentence. Two sentence!", "sentence") == ["One sentence.", "Two sentence!"]
    assert len(chunk_text("أول جزء, ثاني جزء", "phrase")) == 2
    assert script_route("ملخص سريع quick") == "ar"
    assert script_route("quick summary ملخص") == "en"


def test_cancellation_epoch_rejects_stale_output():
    epoch = CancellationEpoch(); first, signal = epoch.begin()
    assert epoch.is_current(first) and not signal.is_set()
    epoch.cancel()
    assert signal.is_set() and not epoch.is_current(first)
    second, _ = epoch.begin()
    assert second > first and epoch.is_current(second)


def test_stream_state_rejects_duplicates_and_out_of_order():
    state = StreamState()
    assert state.accept("a", 2)
    assert not state.accept("a", 3)
    assert not state.accept("b", 1)
    assert state.duplicates == 1 and state.stale == 1


def test_bounded_ingress_backpressure_and_shutdown():
    from horus_local_voice.streaming import AudioChunk, BoundedAudioIngress
    ingress = BoundedAudioIngress(2); ingress.start()
    assert ingress.push(AudioChunk(1, 1, b"a"))
    assert ingress.push(AudioChunk(2, 2, b"b"))
    assert not ingress.push(AudioChunk(3, 3, b"c")) and ingress.dropped == 1 and ingress.depth == 2
    assert ingress.pop().sequence == 1
    ingress.shutdown(); assert ingress.state == "STOPPED" and not ingress.push(AudioChunk(4, 4, b"d"))


def test_pipelined_responder_synthesizes_before_full_completion():
    emitted = []
    pipeline = PipelinedResponder(lambda text: text.encode(), emitted.append, max_chars=20)
    result = pipeline.run(iter(["First sentence.", " Second one."]), "sentence")
    assert result.text_chunks == 2 and result.audio_chunks == 2
    assert emitted[0] == b"First sentence."


def test_pipelined_responder_drops_audio_after_cancel():
    emitted = []
    pipeline = PipelinedResponder(lambda text: (pipeline.cancel(), text.encode())[1], emitted.append)
    result = pipeline.run(iter(["Cancel now."]))
    assert result.cancelled and emitted == []


def test_stream_session_starts_and_stops_bounded_queue():
    from horus_local_voice.streaming import AudioChunk, StreamSession
    session = StreamSession("test", queue_size=1)
    session.start()
    assert session.state == "listening"
    assert session.queue.push(AudioChunk(1, 1, b"frame"))
    assert not session.queue.push(AudioChunk(2, 2, b"overflow"))
    assert session.queue.high_water == 1 and session.queue.dropped == 1
    session.stop()
    assert session.state == "stopped" and session.queue.depth == 0


def test_stream_session_recovery_records_component():
    from horus_local_voice.streaming import StreamSession
    session = StreamSession("recover")
    session.start()
    session.recover("stt")
    assert session.restarts == 1
    assert session.metrics[-1]["component"] == "stt"


def test_audio_chunk_compatibility_timestamp_property():
    from horus_local_voice.streaming import AudioChunk
    chunk = AudioChunk(sequence=3, captured_ns=99, pcm=b"x", sample_rate=8000)
    assert chunk.captured_at_ns == 99 and chunk.sample_rate == 8000
