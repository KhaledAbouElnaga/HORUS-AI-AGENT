# Milestone 3 Evaluation Data

## Current fixture set

- 3 Egyptian-Arabic-labelled FLEURS samples from `MohamedRashad/fleurs-ar-eg`.
- 2 formal-Arabic-text samples from the same public set; speaker dialect is not independently established.
- 2 English LibriSpeech dummy samples from `hf-internal-testing/librispeech_asr_dummy`.
- 1 mixed fixture concatenating one Arabic and one English WAV; explicitly not a natural code-switch recording.

Downloader: `python scripts/download_fixtures.py`. Audio is normalized to mono, 16 kHz, 16-bit PCM. Downloaded audio/models remain ignored local artifacts and are not committed.

## Egyptian conversational search boundary

The searched `NightPrince/MasriSpeech` route was not consumable through the public datasets-server in this environment (HTTP 404/401). No credentials were supplied and no gated access was bypassed. Therefore Egyptian conversational quality is not claimed; the current set is reproducible but read-speech biased.

## Sources and licenses

- FLEURS-derived dataset: https://huggingface.co/datasets/MohamedRashad/fleurs-ar-eg
- LibriSpeech dummy fixture: https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy
- faster-whisper: https://github.com/SYSTRAN/faster-whisper (MIT implementation; model terms remain applicable)
- Piper voices/engine: https://github.com/OHF-Voice/piper1-gpl (engine/voice licenses must be reviewed per redistribution)
- TinyLlama model: https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0 (Apache-2.0 model card)
- llama.cpp: https://github.com/ggml-org/llama.cpp (MIT)

## Additional public-data attempts

Yahya-Mohamed/egyptian-arabic-speech-dataset was inspected: it exposes precomputed input_features and token labels, not reusable raw speech/transcripts, and its card states no license. xtz999/egyptian_arabic_speech_zaid was inspected but its card also states no license. Neither was imported. The concatenated mixed fixture remains explicitly synthetic rather than natural code-switch speech.

- Qwen 0.5B GGUF: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF
- Qwen 1.5B GGUF: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- Both repositories state Apache-2.0.

## Additional public-data attempts

Yahya-Mohamed/egyptian-arabic-speech-dataset was inspected: it exposes precomputed input features and token labels, not reusable raw speech and transcripts, and its card states no license. xtz999/egyptian_arabic_speech_zaid was inspected but its card also states no license. Neither was imported. The concatenated mixed fixture remains explicitly synthetic rather than natural code-switch speech.

- Qwen 0.5B GGUF: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF
- Qwen 1.5B GGUF: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- Both repositories state Apache-2.0.
