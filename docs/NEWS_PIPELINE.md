# Current-news pipeline

Research and live verification date: **2026-09-11**.

## Design

Morgonkoll uses a curated allowlist rather than searching or executing
arbitrary web content:

1. Fetch RSS/Atom over HTTPS with bounded responses, timeouts, conditional
   requests and a six-hour emergency cache.
2. Strip markup, reject advertisements/configured non-news titles and keep only
   entries from the latest 36 hours.
3. Cluster similar headlines, rank recency/relevance/source quality, enforce
   topic quotas and limit repeated use of one source.
4. Fetch article text only for source types explicitly approved for it, only
   when `robots.txt` permits, and cap extracted text at 6,000 characters.
5. Treat all downloaded text as untrusted data. It is never executed and cannot
   give the model instructions.
6. Generate small source-bound sections locally, then run a separate local
   support check for every section.
7. Reject unknown story IDs, unsupported numbers, URLs and invalid total
   length. Preserve selected stories and source links beside the script.

If local generation fails, the workflow emits a clearly identified,
metadata-only reserve notice rather than copying article/feed prose, calling a
paid API or inventing a normal episode.

## Reviewed sources

All URLs returned HTTP 200 with valid RSS/Atom and no login/API key when checked.
Counts and publishing frequency can change.

| Topic | Source | Feed | Role |
|---|---|---|---|
| General | SVT Nyheter | `https://www.svt.se/rss.xml` | Swedish public broadcaster |
| World | SVT Utrikes | `https://www.svt.se/nyheter/utrikes/rss.xml` | Swedish public broadcaster |
| General/world | Sveriges Radio Ekot | `https://api.sr.se/api/rss/program/83?format=145` | Swedish public broadcaster; API is unmaintained but available |
| Breaking | Aftonbladet | `https://rss.aftonbladet.se/rss2/small/pages/sections/senastenytt/` | Swedish editorial fallback |
| General | Expressen | `https://feeds.expressen.se/nyheter/` | Swedish editorial fallback |
| Economy | SVT Ekonomi | `https://www.svt.se/nyheter/ekonomi/rss.xml` | Public-broadcaster category |
| Economy | EFN | `https://efn.se/rss` | Swedish economy/markets |
| Statistics | SCB | `https://www.scb.se/feed/statistiknyheter` | Primary official statistics |
| Monetary policy | Riksbanken | `https://www.riksbank.se/sv/rss/pressmeddelanden/` | Primary official source |
| Technology | Computer Sweden | `https://computersweden.se/feed/` | Swedish editorial source |
| Technology | Ny Teknik | `https://www.nyteknik.se/index?lab_viewport=rss` | Swedish editorial source; ads filtered |
| AI | OpenAI News | `https://openai.com/news/rss.xml` | First-party company claims |
| AI research | Google DeepMind | `https://deepmind.google/blog/rss.xml` | First-party company claims |
| Gaming/digital | SweClockers | `https://www.sweclockers.com/feeds/nyheter` | Swedish editorial source |
| Games industry | Dataspelsbranschen | `https://www.dataspelsbranschen.se/feed/` | Swedish industry-primary source |

`config/news_sources.yml` is the executable source of truth. Company and
authority feeds carry lower editorial weights and are explicitly labeled
`primary`, so the script says who is making the claim.

## Copyright policy

Public feed access is not a republication license. The system:

- identifies facts and writes a new Swedish summary;
- names publishers in source metadata and preserves direct article links;
- does not reuse feed images, audio or video;
- does not bypass paywalls;
- does not publish stored article bodies;
- uses quotations only if short and necessary; and
- does not imply endorsement or affiliation.

Feed and article prose remain the publishers' material unless a source states
otherwise. SCB open data is CC0, but that does not automatically license every
photograph or editorial passage on its website.

## Local script model

The automatic model is
[`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) using the
well-established Bartowski conversion
[`Qwen_Qwen3.5-4B-Q4_K_M.gguf`](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF):

- Apache-2.0
- multilingual instruction model with 201 documented languages
- 4B parameters, Q4_K_M, 3,013,027,808 bytes
- repository revision
  `4168f45a16a1290d65a4ec0fa312ae917a4c15d6`
- SHA-256
  `13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983`
- CPU-only llama.cpp execution with an 8,192-token working context

The workflow verifies repository revision, exact size and SHA-256 before
loading. It uses a fixed ChatML template rather than executing the GGUF's
embedded template. Current third-party EuroEval results show materially strong
Swedish facts and sentiment performance for the full-precision base model;
those results demonstrate language competence but do not replace this
project's quantized end-to-end acceptance run.

## Artifacts and failure behavior

Each run writes:

- `sources.md`
- `sources.json` (titles, timestamps and links; no copied article bodies)
- `script.txt`
- `manifest.json`
- `morgonkoll-YYYY-MM-DD.mp3`

The manifest records feed/enrichment errors, selected-source count, generator,
word count and fallback reason. Fewer than six stories or four independent
sources stops the run. TTS retains its own free-only fallback policy.
