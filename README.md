# Morgonkoll

Morgonkoll turns a Swedish text script into a normalized, tagged podcast MP3
using only local, free-to-download speech models. It calls no metered speech
API, needs no billing account or credit card, and has no paid fallback.

The current human-selected voice is **Piper Alma medium
(`sv_SE-alma-medium`)**. The restorable automatic default is **Kokoro Swedish
`Stina`**. Both have
permissively licensed voice weights and run on the conservative 2-vCPU/8-GB
GitHub runner envelope. **Chatterbox Multilingual V3** remains available for
human audition, but its CPU runtime is too risky for the daily default.

## Quick start

Prerequisites: Python 3.11 and `ffmpeg`/`ffprobe`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install ".[production]"

# Replace content/script.txt with today's human-readable Swedish script.
python -m src.health_check
python -m src.pipeline --script content/script.txt --date 2026-09-10
python -m src.verify_audio output/morgonkoll-2026-09-10.mp3
```

The first run downloads the selected model. Later runs reuse the Hugging Face
cache. Set `HF_HOME` and `MORGONKOLL_CACHE_DIR` if the cache should live
somewhere specific.

The output is `output/morgonkoll-YYYY-MM-DD.mp3`. The source script is never
rewritten. Pronunciation-friendly text is generated separately at
`build/narration.txt`.

## Daily operation

1. Put the final Swedish editorial script in `content/script.txt`.
2. Optionally add a square JPEG at `assets/cover.jpg`.
3. Run the **Generate Morgonkoll** workflow manually, or let it run every day
   at 06:00 in the `Europe/Stockholm` timezone.
4. The episode is sent to your Telegram chat and also retained as a downloadable
   Actions artifact.

The bundled `content/script.txt` is clearly marked demonstration material; it
is long enough for a realistic smoke test but is not current news.

Before synthesis the workflow loads the selected engine and exact pinned model.
If it is unavailable, the pipeline retries the listed free local fallback. If
all approved voices fail, it stops with:

> No compatible free TTS voice is currently available. No paid service was used.

### One-time phone delivery setup

Telegram delivery is free and does not require the Mac to be online, but you
must create your private bot credentials once:

1. In Telegram, open the verified **@BotFather**, send `/newbot`, follow the
   prompts and copy the bot token. Do not paste that token into chat or commit
   it to this repository.
2. Open your new bot in Telegram and send it a message such as `Hej`.
3. In a local terminal, set the token temporarily and inspect the bot updates:

   ```bash
   export TELEGRAM_BOT_TOKEN='token-from-BotFather'
   curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates"
   ```

   Copy the numeric value under `message.chat.id`.
4. After publishing the repository, add two GitHub Actions repository secrets:
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
5. Run **Generate Morgonkoll** manually once and confirm that the audio arrives.

`src.telegram_delivery` validates the final MP3 before upload and uses
Telegram's `sendAudio` endpoint. It never logs the bot token. The workflow also
retains the MP3 as an artifact if Telegram delivery fails.

## Choosing the best free voice

Copilot selected **Kokoro Swedish `Stina`** after current research uncovered
this July 2026 Swedish-specific release. It is an 82M-parameter model trained
over 23 real Swedish speakers, includes a neural Swedish G2P and ten voice
packs, and uses Apache-2.0 code and weights derived from CC0 Swedish data. Exact
code, voice-model and G2P revisions are pinned and checked before loading.
Stina's fixed sample scored 8.47/10, ran at 153 WPM, took about 12.6 seconds to
synthesize, and had no clipping. The 1,346-word bundled long-form script
completed as 55 semantic chunks in 2:12 on local Apple CPU, peaked at 2.72 GB
resident memory, and produced an 8:42 MP3. A later repeat was heavily delayed by
local host scheduling/sleep and took 55 minutes wall time while consuming about
8 minutes of CPU; the workflow therefore keeps a conservative 120-minute limit.

| Voice | License | Approx. weights | Measured one-minute sample | Swedish/practical assessment |
|---|---|---:|---:|---|
| Kokoro Swedish Stina | Apache-2.0 | 372 MB selected files | 12.6 s CPU | Automatic winner; Swedish neural G2P and responsive prosody |
| Piper Alma medium | CC-BY-4.0 weights; GPL engine | 63.4 MB | about 3 s CPU | Explicitly licensed native-Swedish fallback |
| Piper NST medium | Repo metadata MIT; card states CC0 data but no separate weight license | 63 MB | 2.8 s CPU | Tested historical lightweight alternative |
| Meta MMS Swedish | CC-BY-NC-4.0 | 145 MB | 7.2 s CPU | Tested personal-use alternative, not the open fallback |
| Chatterbox Multilingual V3 | MIT; watermarked output | 3.0 GB | 509–636 s CPU | Naturalness experiment; too slow for daily 2-vCPU use |

Full research, rejected alternatives, exact revisions and source links are in
[`docs/VOICE_RESEARCH.md`](docs/VOICE_RESEARCH.md).

### Automatic benchmark

```bash
# Benchmarks production-safe voices, writes identical samples and selects the
# highest successful engineering score.
python -m src.voice_benchmark

# Add optional local Swedish ASR as an intelligibility signal.
python -m pip install ".[asr]"
python -m src.voice_benchmark --with-asr

# List the entire curated registry, including exclusions.
python -m src.voice_benchmark --list
```

Samples are written to `voice_samples/` as Candidate A, Candidate B and so on.
The benchmark report clearly separates measured audio properties from
maintained subjective evidence. Automated metrics cannot determine whether a
voice is pleasant for eight minutes.

### Human audition

Run **Voice audition** from GitHub Actions. It installs every viable candidate
that fits the detected runner, synthesizes the exact same Swedish script,
optionally transcribes the samples locally, and uploads the MP3 files plus
Markdown/JSON reports.

**Listen to the samples and choose the voice you like most.**

Apply a choice without editing JSON:

```bash
python -m src.select_voice chatterbox-multilingual-v3
```

Alternatively, set repository variables `TTS_ENGINE`, `TTS_MODEL` and
`TTS_VOICE`, or edit `config/selected_voice.json`. Values must identify one
viable registry entry; they are not arbitrary remote model names.

Restore Copilot's automatic selection:

```bash
python -m src.select_voice --restore-automatic
```

The separate **Find a better free voice** workflow runs quarterly and on
request. It audits maintained source links and produces new samples and a
recommendation, but never changes the stable voice automatically.

## Narration and audio behavior

- `config/pronunciations.yml` changes difficult names only in the generated
  narration copy. Correct spelling stays in the editorial source.
- Paragraph-aware chunks stay below engine limits. Heading, paragraph and
  sentence boundaries receive explicit natural pauses.
- Each segment is trimmed only at its outer edges, converted to mono 44.1 kHz
  PCM and concatenated losslessly before encoding.
- ffmpeg performs measured two-pass EBU R128 normalization to -19 LUFS, limits
  true peak to -1.5 dBTP, and encodes 128 kbit/s mono MP3.
- ID3v2.3 metadata includes episode title, show title, artist and date. A
  supplied cover is embedded as an attached picture.
- Files are written atomically so a failed encode cannot leave a plausible
  partial episode.

Speaking rate is a native engine parameter where available; no final audio is
blindly time-stretched. A normal script
should contain roughly 1,100–1,350 spoken words for a 7–9 minute episode.
When an episode consistently misses that range, adjust future editorial length
instead of aggressively stretching the finished recording.

## GitHub Actions cost and resources

All TTS generation is local to `ubuntu-latest`; no GPU, larger runner,
self-hosted machine or commercial API is used. GitHub currently documents:

| Repository | CPU | RAM | SSD | Standard-runner charging |
|---|---:|---:|---:|---|
| Public | 4 vCPU | 16 GB | 14 GB | Free and unlimited |
| Private | 2 vCPU | 8 GB | 14 GB | Uses included minutes, then may be billed |

The project itself cannot guarantee zero GitHub billing after a private
account's included minutes are exhausted. For strict zero spend, use a public
repository where appropriate, or set the account's Actions spending limit to
zero. Model generation itself always costs 0 SEK and cannot transition to a
paid inference service.

This greenfield folder had no GitHub remote, so an actual hosted
`ubuntu-latest` job could not be dispatched during implementation. The three
workflow files parse as valid YAML, use the documented runner, install only
Linux-supported local packages, and target the conservative private-runner
resources. The first run after publishing should be the **Voice audition**
workflow; its measured output is the final hosted-runner confirmation.

Models are cached with keys derived from the candidate registry, selected voice
and dependency manifest. Large downloaded weights, generated audio, raw chunks,
personal reference recordings and caches are excluded by `.gitignore`.

## Development

```bash
python -m pip install ".[test,piper]"
python -m pytest
```

Critical tests cover deterministic selection order, environment override
validation, pronunciation isolation, semantic chunking, free-only fallback,
real ffmpeg concatenation/normalization/tagging, cover attachment, MP3
verification and benchmark pacing.

Important files:

| Path | Purpose |
|---|---|
| `config/voice_candidates.yml` | Curated candidates, licenses, exact revisions and runner constraints |
| `config/selected_voice.json` | Stable production selection and fallback order |
| `config/automatic_voice.json` | Restore point for Copilot's automatic choice |
| `config/pronunciations.yml` | Narration-only substitutions |
| `src/voice_benchmark.py` | Fixed-sample generation, metrics, report and automatic selection |
| `src/pipeline.py` | Health-aware long-form synthesis and fallback |
| `src/audio.py` | ffmpeg preparation, normalization, metadata and verification |
| `.github/workflows/voice-audition.yml` | Optional human comparison |
| `.github/workflows/find-better-voice.yml` | Periodic curated re-evaluation |
