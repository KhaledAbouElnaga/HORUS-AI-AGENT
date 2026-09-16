# Real Local Speech Results

**Commands:** `python scripts/download_fixtures.py`, `python scripts/run_real_stt.py`, `python scripts/run_real_tts.py`, `python scripts/run_real_pipeline.py`

**STT:** faster-whisper `tiny`, CPU `int8`, 8 actual PCM WAV files. **TTS:** Piper 1.8.0 with `ar_JO-kareem-medium` and `en_US-lessac-medium`. The WAV outputs are playable and remain local/ignored; the downloader reproduces them without credentials.

| Fixture | Expected reference | Observed transcript | WER | STT ms |
|---|---|---|---:|---:|
| Egyptian 01 | تشكلت في المحيط الأطلسي اليوم عاشر عاصفة مُسماة لموسم الأعاصير الأطلسية العاصفة شبه الاستوائية جيري | دشكلات في المهيد الأطلاص اليوم عشر عاصفة مسمي لموسي من العاصر الأطلاصية العاصفة شبه الاستوائية الجري | 0.6667 | 592.43 |
| Egyptian 02 | تغادر الحافلات المحطة الداخلية بين المناطق عبر النهر في خلال اليوم على الرغم من أن معظمها وخاصة المتجهة منها إلى الشرق وجاكار/بومثانج تغادر بين 06:30 و 07:30 | تغادر حثلات المحطة دخلية بين المنوتق عبر النهر في خلال اليوم على الرغم من أننا معظمها وخصة المتغة منها إلى الشرق وجاكارة بومثان تغادر بين ستو تلاتين وسبعة وتلاتين | 0.4333 | 633.96 |
| Egyptian 03 | يتمُّ دعم التعلُّم التفاعليّ في البرنامج داخليًا ويهدف إلى طرح الأسئلة والتحفيز وشرح الإجراءاتِ التي قد يكون من الصعب على الطالب التعامل معها بمفرده | يتم مدعم التعالل من التفعلي في البرنامج داخلياً ويهدف إلى طرح العسئلة والتحفز وشارح الإجراطة التي قديقون من الصابع للطالب اتعام المعهاب مفرده | 0.6667 | 598.32 |
| MSA-text 01 | تشكلت في المحيط الأطلسي اليوم عاشر عاصفة مُسماة لموسم الأعاصير الأطلسية العاصفة شبه الاستوائية جيري | دشكلات في المهيد الأطلاص اليوم عشر عاصفة مسمي لموسي من العاصر الأطلاصية العاصفة شبه الاستوائية الجري | 0.6667 | 599.06 |
| MSA-text 02 | تغادر الحافلات المحطة الداخلية بين المناطق عبر النهر في خلال اليوم على الرغم من أن معظمها وخاصة المتجهة منها إلى الشرق وجاكار/بومثانج تغادر بين 06:30 و 07:30 | تغادر حثلات المحطة دخلية بين المنوتق عبر النهر في خلال اليوم على الرغم من أننا معظمها وخصة المتغة منها إلى الشرق وجاكارة بومثان تغادر بين ستو تلاتين وسبعة وتلاتين | 0.4333 | 710.23 |
| English 01 | MISTER QUILTER IS THE APOSTLE OF THE MIDDLE CLASSES AND WE ARE GLAD TO WELCOME HIS GOSPEL | Mr. Kilder is the apostle of the middle classes and we are glad to welcome his gospel. | 0.1176 | 668.60 |
| English 02 | NOR IS MISTER QUILTER'S MANNER LESS INTERESTING THAN HIS MATTER | Nor is Mr. Quilters' manner less interesting than his matter. | 0.2727 | 572.49 |
| Mixed (composed) | Arabic 01 + English 01 | دشكلات في المهيدة الأطلاص اليوم عشرة عوسيفة مسمي لموسي من الأوسير الأطلاصية على عوسيفة شبه الاستوائية الجري | 0.9375 | 642.71 |

The MSA-text files use formal reference sentences from the available `fleurs-ar-eg` source; speaker dialect is not independently verified. The mixed file is intentionally documented as concatenated real clips, not natural code-switch speech. Latest 20-turn pipeline summary: mean WER 0.5411, STT p95 1075.13 ms, TTS first-audio p95 368.06 ms, end-to-end p95 1428.56 ms, cold STT model load 965.50 ms after cache, voice load 3519.07 ms, RSS 481.3 MB, CPU-only.

Standalone TTS run: Arabic synthesis 1841.95 ms for 3.669 s output; English synthesis 87.74 ms for 1.974 s output. Hardware microphone/speaker latency was not measured.
