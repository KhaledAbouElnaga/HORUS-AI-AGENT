# Milestone 2 Real Local Speech Results

Commands: python scripts/download_fixtures.py; then run each real script with PYTHONPATH=src.

## STT transcripts

faster-whisper 1.2.1, CTranslate2 4.8.1, tiny, CPU/int8. Cache size: 156,408,143 bytes.

| Fixture | Expected | Observed | WER | ms | detected |
|---|---|---|---:|---:|---|
| egyptian_arabic_01.wav | تشكلت في المحيط الأطلسي اليوم عاشر عاصفة مُسماة لموسم الأعاصير الأطلسية العاصفة شبه الاستوائية جيري | دشكلات في المهيد الأطلاص اليوم عشر عاصفة مسمي لموسي من العاصر الأطلاصية العاصفة شبه الاستوائية الجري | 0.6667 | 507.09 | ar |
| egyptian_arabic_02.wav | تغادر الحافلات المحطة الداخلية بين المناطق عبر النهر في خلال اليوم على الرغم من أن معظمها وخاصة المتجهة منها إلى الشرق وجاكار/بومثانج تغادر بين 06:30 و 07:30 | تغادر حثلات المحطة دخلية بين المنوتق عبر النهر في خلال اليوم على الرغم من أننا معظمها وخصة المتغة منها إلى الشرق وجاكارة بومثان تغادر بين ستو تلاتين وسبعة وتلاتين | 0.4333 | 528.15 | ar |
| egyptian_arabic_03.wav | يتمُّ دعم التعلُّم التفاعليّ في البرنامج داخليًا ويهدف إلى طرح الأسئلة والتحفيز وشرح الإجراءاتِ التي قد يكون من الصعب على الطالب التعامل معها بمفرده | يتم مدعم التعالل من التفعلي في البرنامج داخلياً ويهدف إلى طرح العسئلة والتحفز وشارح الإجراطة التي قديقون من الصابع للطالب اتعام المعهاب مفرده | 0.6667 | 509.26 | ar |
| arabic_msa_01.wav | نصنع بيوتنا وملابسنا من النباتات . معظم الطعام الذي نتناوله من النباتات كذلك. بدون النباتات، لا يمكن للحيوانات البقاء | نسنا بيوتنا وملا بسنا من النباتات موزم الطعام الذي نتنا ولهم من النباتات كذلك بدون النباتات لا يمكن الحياة ونات البقاب | 0.5000 | 645.70 | ar |
| arabic_msa_02.wav | إن عرض الصوت والضوء الهرمي واحد من أمتع الأشياء الموجودة بالمنطقة للأطفال | إنا عرض السوت والدوء الهرم يوحد من أمتع الأشياء الموجودة بالمنتقال الأطفال | 0.5833 | 798.08 | ar |
| english_01.wav | MISTER QUILTER IS THE APOSTLE OF THE MIDDLE CLASSES AND WE ARE GLAD TO WELCOME HIS GOSPEL | Mr. Kilder is the apostle of the middle classes and we are glad to welcome his gospel. | 0.1176 | 748.22 | en |
| english_02.wav | NOR IS MISTER QUILTER'S MANNER LESS INTERESTING THAN HIS MATTER | Nor is Mr. Quilters' manner less interesting than his matter. | 0.2727 | 751.16 | en |
| mixed_ar_en.wav | تشكلت في المحيط الأطلسي اليوم عاشر عاصفة مُسماة لموسم الأعاصير الأطلسية العاصفة شبه الاستوائية جيري MISTER QUILTER IS THE APOSTLE OF THE MIDDLE CLASSES AND WE ARE GLAD TO WELCOME HIS GOSPEL | دشكلات في المهيدة الأطلاص اليوم عشرة عوسيفة مسمي لموسي من الأوسير الأطلاصية على عوسيفة شبه الاستوائية الجري | 0.9375 | 834.56 | ar |

Mean WER across eight fixture files: 0.5222. The three Egyptian-labeled files are ar-EG FLEURS read speech, not conversational Egyptian. The two MSA-labeled files are distinct later rows with formal Arabic text from the same ar-EG source. The mixed file concatenates real Arabic and English clips; tiny Whisper omitted its English half. No dialect-quality claim is made.

## TTS

Piper TTS 1.8.0 / ONNX Runtime 1.27.0, CPU. Each output is a playable local WAV.

| Case | Voice | model bytes | load ms | first audio ms | synthesis ms | output s | RSS MB |
|---|---|---:|---:|---:|---:|---:|---:|
| egyptian_arabic | ar_JO-kareem-medium | 63201294 | 1637.53 | 709.52 | 709.53 | 3.947 | 232.7 |
| msa | ar_JO-kareem-medium | 63201294 | 0.00 | 340.28 | 340.29 | 3.355 | 233.4 |
| english | en_US-lessac-medium | 63201294 | 3645.07 | 321.52 | 321.54 | 1.904 | 351.7 |

Voice sources/model cards:
- Arabic/Jordanian Kareem: https://huggingface.co/rhasspy/piper-voices/tree/main/ar/ar_JO/kareem/medium. Model card points to arabicttstrain and says to consult that source for licensing.
- English US Lessac: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium. Model card links the Lessac Blizzard 2013 license.
- Redistribution licensing is not asserted; models and generated artifacts remain git-ignored.

## Limits and failures

- Physical microphone and speaker devices were enumerated, but unattended recording/playback was not performed; hardware latency is NOT MEASURED.
- Real local agent path is BLOCKED: no pre-existing Ollama, llama.cpp, llama-cpp-python, Transformers, or Torch runtime/model was found.
- Corrupt/unsupported and missing WAV input fail closed in automated tests.
- An earlier unbounded Arabic transcript TTS attempt raised ONNX Runtime bad allocation; the bounded agent response recovered and completed.
- STT/TTS timeout injection and forced model corruption remain NOT MEASURED rather than claimed PASS.
- Meta/WhatsApp systems, existing HORUS runtime, credentials, providers, routing, billing, and paid services were not touched.
