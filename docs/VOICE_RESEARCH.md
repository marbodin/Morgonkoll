# Swedish local TTS research

Research date: **2026-09-10**. This is a maintained decision record, not a
live claim that a scheduled script can discover every new model on the
internet.

## Decision

**Automatic daily voice: Kokoro Swedish `Stina`.** The current Swedish-specific
release uses an 82M Kokoro model, a neural Swedish G2P and ten voices derived
from 23 real Swedish speakers. Its code and weights are Apache-2.0, its Swedish
datasets are CC0, and its selected files total about 372 MB. It produced the
strongest tested automatic score while remaining safe on the minimum standard
GitHub-hosted Linux runner: 2 vCPU, 8 GB RAM and 14 GB SSD for private
repositories.

**Free/open fallback: Piper `sv_SE-alma-medium`.** Alma's model card explicitly
licenses its weights under CC-BY-4.0. It is only 63.4 MB, native Swedish and
substantially faster than real time.

**High-quality audition candidate: Chatterbox Multilingual V3.** Its official
repository explicitly includes Swedish among 23 languages, calls V3 the
recommended multilingual model, identifies it as 500M parameters, and uses an
MIT license. It generated the fixed sample successfully and received the
highest evidence-weighted score. It is not the unattended default because the
one-minute sample took 488.8 seconds on local CPU. An eight-minute episode could
take well over an hour on a 2-vCPU x64 runner, with less margin for retries.

**Tested non-commercial alternative: Meta MMS Swedish.** It completed the
benchmark but its CC-BY-NC-4.0 weights are not used as the open fallback.

## What was actually measured

The fixed text contains 144 written words and 154 words after narration-only
pronunciation expansion. Final measurements below use the calibrated native
speaking-rate controls; signal checks happen after MP3 normalization.

| Candidate | Swedish basis | Model/download | Fixed sample | Local CPU synthesis | Peak RSS | Result |
|---|---|---:|---:|---:|---:|---|
| Kokoro Swedish Stina | 23 Swedish speakers + neural G2P | 372 MB selected files | 56.7 s, 153.4 WPM | 12.6 s | under 2.5 GB in four-candidate run | Daily winner |
| Kokoro Swedish Alice | Same pinned model/voice pack | voice shares base | 58 s target after rate calibration | about 12 s | shares model footprint | Audition |
| Kokoro Swedish Björn | Same pinned model/voice pack | voice shares base | 58 s target after rate calibration | about 13 s | shares model footprint | Audition |
| Piper Alma medium | Native Swedish/NST | 63.4 MB | native rate calibrated toward 155 WPM | about 3 s | under 0.5 GB expected | Open fallback |
| Piper NST medium | Native Swedish, KBLab/NST | 63.2 MB | 58.3 s, 158.4 WPM | 2.8 s | under 0.5 GB in its isolated run | Alternative |
| Meta MMS Swedish | Dedicated Swedish checkpoint | about 145 MB | 57.6 s, 160.6 WPM | 7.2 s | 1.55 GB for an earlier combined run | Non-commercial alternative |
| Chatterbox Multilingual V3 | Official Swedish support | 3.0 GB downloaded weights | 56.8 s, 162.7 WPM | 509–636 s | 3.34 GB isolated; 4.39 GB in ASR audition | Optional audition |

Exact current measurements are written to
`voice_samples/comparison_report.json` whenever
`python -m src.voice_benchmark` runs. Runtime measurements are machine-specific;
they are evidence for feasibility, not a promise about GitHub's shared x64 CPU.

The selected Stina voice also completed the bundled 1,346-word long-form script
as 55 semantic chunks. Synthesis, concatenation, normalization, tagging and
verification took 132 seconds locally, peaked at 2.72 GB resident memory, and
produced an 8:42, 8.35 MB MP3.

A repeat generated the same 8:42 result but took 55 minutes of wall time while
the local host was substantially descheduled/asleep (about 8 minutes of CPU
time). This is not treated as an engine regression, but it supports the
conservative 120-minute daily timeout. No GitHub remote existed for this folder,
so the workflows could not be dispatched on a real `ubuntu-latest` host during
implementation; that hosted execution remains the one environment-specific
confirmation step.

The weighted score follows the brief: 40% Swedish naturalness, 20%
pronunciation, 15% prosody/rhythm, 10% long-listening pleasantness, and 5% each
for consistency, reliability and practicality. Documented language capability
and a maintained human assessment supply the subjective priors. Generated
audio contributes pace, silence, clipping and runtime. Optional Swedish ASR
adds an intelligibility signal. This method **cannot objectively determine**
whether a voice is warm, natural or pleasant; the manual audition is the final
authority for those properties.

## Primary evidence

- The pinned [Kokoro Swedish source](https://github.com/joakimeriksson/kokoro-sv/tree/42d1a3a5c083f405a6eb8e14c2a405ccb36cc90f)
  documents an 82M Swedish model, neural G2P, ten voice packs, 23 real speakers,
  CC0 data and Apache-2.0 licensing.
- The pinned [Kokoro Swedish voice model](https://huggingface.co/Joakim/kokoro-sv-voices/blob/2c7968d59c2fda1667e9e3ff0dd9967150a53f74/README.md)
  records the ten voices, measured prosody responsiveness and known v1 comb
  artifacts. The separate pinned G2P revision is
  `a5aac876ccb2bf7480a129774c7e89cf3bbeac01`.
- [Piper engine](https://github.com/OHF-Voice/piper1-gpl) is a local ONNX TTS
  engine. The current engine is GPL-3.0-or-later.
- The pinned [Piper Alma card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/sv/sv_SE/alma/medium/MODEL_CARD)
  explicitly says Swedish, 22,050 Hz and CC-BY-4.0 model weights.
- The pinned [Piper NST model card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/sv/sv_SE/nst/medium/MODEL_CARD)
  says Swedish (`sv_SE`), one speaker, 22,050 Hz, trained by KBLab from the
  CC0 NST dataset. The containing model repository declares MIT.
- The pinned [MMS Swedish model card](https://huggingface.co/facebook/mms-tts-swe/blob/62c98ce783f0a4c127d35300bca120dbdf03ad93/README.md)
  identifies a dedicated Swedish VITS checkpoint and CC-BY-NC-4.0.
- The pinned [Chatterbox V3 source](https://github.com/resemble-ai/chatterbox/tree/5de7a54aa4e5e2baadb0182dde554908b48b85c2)
  documents Swedish support, the 500M multilingual model, CPU support, MIT
  licensing and built-in PerTh watermarking. The adapter pins this exact source
  commit because the PyPI `0.1.7` wheel did not yet expose the documented V3
  loader during testing.
- [GitHub-hosted runner resources](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
  define the runner envelope. GitHub also explains that public standard runners
  are free and unlimited, while private repositories consume included minutes
  and can incur charges after quota in its
  [billing documentation](https://docs.github.com/en/actions/concepts/billing-and-usage).

## Evaluated but not selected

| Family | Finding |
|---|---|
| Generic Kokoro 82M | The base model has no Swedish voice, but the new Apache-licensed Kokoro Swedish fine-tune is now selected. |
| Community Coqui Swedish VITS | A BSD-licensed 2022 checkpoint exists, but current-toolkit compatibility and modern listening quality are unverified. |
| XTTS v2 | Official language support does not list Swedish; the model is also much heavier than native VITS options. |
| MeloTTS | Official language list does not include Swedish. |
| Parler-TTS | No maintained official Swedish checkpoint was verified; multilingual checkpoints are too heavy to justify speculative use. |
| F5-TTS | No official Swedish-quality checkpoint was established, and diffusion CPU inference is a poor standard-runner default. |
| Fish Speech | Resource requirements and research model terms do not meet this stable zero-cost runner target. |
| StyleTTS 2 | No maintained official Swedish checkpoint was verified. |
| SpeechT5 Swedish | MIT fine-tune is runnable in principle, but stale evaluation and manual character transliteration make it a lab candidate only. |
| OmniVoice | Documents Swedish, but weights are CC-BY-NC and CPU practicality is unproven. |
| Qwen3-TTS 0.6B | Apache-licensed, but the official language list does not include Swedish. |
| Meta MMS Swedish | Viable and tested, but lower evidence-weighted quality and non-commercial licensing. |
| Chatterbox V3 | Viable and tested; best audition candidate, but too slow for the conservative unattended default. |

The complete machine-readable reasoning, exact revisions, model paths and
licenses live in `config/voice_candidates.yml`.

## Re-evaluation policy

The registry is deliberately curated. `find-better-voice.yml` checks every
declared primary-source link, benchmarks viable entries, generates samples and
reports whether an alternative appears materially better. It does not scrape
search results and does not replace `selected_voice.json`. A new model should
be added only after:

1. official Swedish support and exact model/voice identifiers are verified;
2. engine, model and dataset licenses are recorded separately;
3. unauthenticated local download and CPU inference are reproduced;
4. download size, peak memory and fixed-sample runtime are measured;
5. the same fixed sample is listened to; and
6. a long-form MP3 completes inside the intended runner envelope.
