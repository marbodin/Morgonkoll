"""Build a self-contained browser audition page from generated voice samples."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "voice_samples" / "comparison_report.json"
OUTPUT = ROOT / "output" / "voice-audition.html"

DESCRIPTIONS = {
    "kokoro-sv-stina": "Uttrycksfull, tydlig och energisk.",
    "kokoro-sv-alice": "Lugnare och mjukare än Stina.",
    "kokoro-sv-bjorn": "Djupare manlig röst med lugnt tempo.",
    "piper-alma-medium": "Rak, tydlig och lättviktig svensk röst.",
    "piper-nst-medium": "Stabil svensk nyhetsröst med enklare prosodi.",
    "mms-swedish": "Mjuk svensk reservröst med jämnt uttryck.",
    "chatterbox-multilingual-v3": "Mer samtalslik och varierad, men mycket långsam att skapa.",
}


def build() -> Path:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    cards = []
    for index, result in enumerate(report["results"], start=1):
        sample_path = ROOT / result["sample"]
        encoded = base64.b64encode(sample_path.read_bytes()).decode("ascii")
        candidate_id = html.escape(result["candidate_id"], quote=True)
        label = html.escape(result["label"])
        description = html.escape(DESCRIPTIONS.get(result["candidate_id"], "Svensk röstkandidat."))
        score = float(result["weighted_score"])
        duration = float(result["metrics"]["duration_seconds"])
        current = result["candidate_id"] == "kokoro-sv-alice"
        card_class = "voice-card current" if current else "voice-card"
        badge = '<span class="badge">Nuvarande</span>' if current else ""
        cards.append(
            f"""
            <article class="{card_class}" data-id="{candidate_id}" data-label="{label}">
              <div class="card-heading">
                <span class="number">{index}</span>
                <div>
                  <h2>{label}</h2>
                  <p>{description}</p>
                </div>
                {badge}
              </div>
              <audio controls preload="metadata" src="data:audio/mpeg;base64,{encoded}"></audio>
              <div class="card-footer">
                <span>{duration:.0f} sekunders identiskt prov</span>
                <span>Tekniskt underlag: {score:.2f}/10</span>
              </div>
              <button type="button" class="choose">Välj {label}</button>
            </article>
            """
        )

    document = f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Välj röst för Morgonkoll</title>
  <script>
    (() => {{
      const param = new URLSearchParams(window.location.search).get("scoutTheme");
      const theme =
        param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
    }})();
  </script>
  <style>
    :root {{
      color-scheme: light;
      --cp-bg: #f7f4ef;
      --cp-bg-elevated: #fcfbf8;
      --cp-surface: #ffffff;
      --cp-surface-soft: #f5f5f5;
      --cp-border: #dedede;
      --cp-border-strong: #919191;
      --cp-text: #242424;
      --cp-text-muted: #5c5c5c;
      --cp-text-soft: #6f6f6f;
      --cp-accent: #b11f4b;
      --cp-accent-hover: #9a1a41;
      --cp-accent-soft: rgba(177, 31, 75, 0.08);
      --cp-accent-fg: #ffffff;
      --cp-success: #16a34a;
      --cp-danger: #dc2626;
      --cp-warning: #f59e0b;
      --cp-link: #0078d4;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
      --cp-overlay: rgba(255, 255, 255, 0.8);
      --cp-panel: rgba(255, 255, 255, 0.86);
      --cp-panel-strong: rgba(255, 255, 255, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.55);
      --cp-highlight: rgba(177, 31, 75, 0.12);
    }}
    html[data-theme="dark"] {{
      color-scheme: dark;
      --cp-bg: #3d3b3a;
      --cp-bg-elevated: #343231;
      --cp-surface: #292929;
      --cp-surface-soft: #2e2e2e;
      --cp-border: #474747;
      --cp-border-strong: #5f5f5f;
      --cp-text: #dedede;
      --cp-text-muted: #919191;
      --cp-text-soft: #b0b0b0;
      --cp-accent: #fd8ea1;
      --cp-accent-hover: #fb7b91;
      --cp-accent-soft: rgba(253, 142, 161, 0.14);
      --cp-accent-fg: #1a1a1a;
      --cp-success: #4ade80;
      --cp-danger: #f87171;
      --cp-warning: #fbbf24;
      --cp-link: #4da6ff;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
      --cp-overlay: rgba(41, 41, 41, 0.88);
      --cp-panel: rgba(41, 41, 41, 0.72);
      --cp-panel-strong: rgba(41, 41, 41, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.04);
      --cp-highlight: rgba(253, 142, 161, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--cp-bg);
      color: var(--cp-text);
      font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0 96px; }}
    header {{ max-width: 760px; margin-bottom: 32px; }}
    .eyebrow {{ color: var(--cp-accent); font-size: 13px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 12px; font-size: clamp(36px, 6vw, 64px); line-height: 1; letter-spacing: -.04em; }}
    header p {{ color: var(--cp-text-muted); font-size: 18px; line-height: 1.55; }}
    .notice {{
      border-left: 4px solid var(--cp-accent);
      background: var(--cp-accent-soft);
      padding: 16px 20px;
      border-radius: 0.625rem;
      margin: 24px 0 36px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .voice-card {{
      background: var(--cp-surface);
      border: 1px solid var(--cp-border);
      border-radius: 16px;
      padding: 20px;
      box-shadow: var(--cp-shadow);
    }}
    .voice-card.current, .voice-card.selected {{ border-color: var(--cp-accent); }}
    .card-heading {{ display: flex; align-items: flex-start; gap: 12px; min-height: 72px; }}
    .number {{
      display: grid; place-items: center; flex: 0 0 32px; height: 32px;
      border-radius: 0.625rem; background: var(--cp-surface-soft); color: var(--cp-text-muted); font-weight: 700;
    }}
    h2 {{ margin: 2px 0 4px; font-size: 19px; }}
    .card-heading p {{ margin: 0; color: var(--cp-text-muted); font-size: 14px; }}
    .badge {{
      margin-left: auto; background: var(--cp-highlight); color: var(--cp-accent);
      border-radius: 0.625rem; padding: 5px 8px; font-size: 12px; font-weight: 700;
    }}
    audio {{ width: 100%; margin: 16px 0 12px; }}
    .card-footer {{ display: flex; justify-content: space-between; gap: 12px; color: var(--cp-text-soft); font-size: 12px; }}
    button {{
      width: 100%; margin-top: 16px; border: 0; border-radius: 0.625rem; padding: 11px 16px;
      background: var(--cp-accent); color: var(--cp-accent-fg); font: inherit; font-weight: 700; cursor: pointer;
    }}
    button:hover {{ background: var(--cp-accent-hover); }}
    .selection {{
      position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%);
      width: min(720px, calc(100% - 32px)); display: none; align-items: center; gap: 16px;
      background: var(--cp-panel-strong); border: 1px solid var(--cp-border-strong);
      border-radius: 16px; padding: 14px 16px; box-shadow: var(--cp-shadow);
    }}
    .selection.visible {{ display: flex; }}
    .selection strong {{ flex: 1; }}
    .selection button {{ width: auto; margin: 0; white-space: nowrap; }}
    #copy-status {{ color: var(--cp-success); font-size: 13px; }}
    @media (max-width: 760px) {{
      main {{ padding-top: 28px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .card-footer {{ flex-direction: column; gap: 4px; }}
      .selection {{ align-items: stretch; flex-direction: column; }}
      .selection button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Morgonkoll · röstprov</div>
      <h1>Vilken röst vill du vakna till?</h1>
      <p>Alla röster läser exakt samma svenska text. Lyssna gärna med hörlurar och välj efter vad som känns behagligt under flera minuter — inte bara efter det tekniska betyget.</p>
    </header>
    <div class="notice"><strong>Tips:</strong> När du startar ett nytt prov pausas det föregående automatiskt. Klicka sedan på <em>Välj</em> och kopiera svaret till chatten.</div>
    <section class="grid">{"".join(cards)}</section>
  </main>
  <aside class="selection" id="selection" aria-live="polite">
    <div>
      <strong id="selected-label"></strong>
      <div id="copy-status">Redo att skickas till Copilot.</div>
    </div>
    <button type="button" id="copy">Kopiera mitt val</button>
  </aside>
  <script>
    const players = [...document.querySelectorAll("audio")];
    players.forEach(player => player.addEventListener("play", () => {{
      players.filter(other => other !== player).forEach(other => other.pause());
    }}));

    let choice = null;
    document.querySelectorAll(".choose").forEach(button => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".voice-card").forEach(card => card.classList.remove("selected"));
        const card = button.closest(".voice-card");
        card.classList.add("selected");
        choice = {{ id: card.dataset.id, label: card.dataset.label }};
        document.getElementById("selected-label").textContent = `Mitt val: ${{choice.label}}`;
        document.getElementById("copy-status").textContent = "Redo att skickas till Copilot.";
        document.getElementById("selection").classList.add("visible");
      }});
    }});

    document.getElementById("copy").addEventListener("click", async () => {{
      if (!choice) return;
      await navigator.clipboard.writeText(`Jag väljer ${{choice.label}} (${{choice.id}}).`);
      document.getElementById("copy-status").textContent = "Kopierat — klistra in texten i chatten.";
    }});
  </script>
</body>
</html>
"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
