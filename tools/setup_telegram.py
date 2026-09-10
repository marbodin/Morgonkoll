"""Securely configure Telegram GitHub secrets and trigger a delivery test."""

from __future__ import annotations

import getpass
import json
import re
import subprocess
import urllib.error
import urllib.request


TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


def _latest_chat(token: str) -> tuple[str, str]:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getUpdates",
        headers={"User-Agent": "Morgonkoll-setup/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Telegram rejected the token (HTTP {exc.code}). Copy the complete token from @BotFather."
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Telegram: {exc.reason}") from exc

    messages = []
    for update in payload.get("result", []):
        for key in ("message", "edited_message", "channel_post"):
            if key in update:
                messages.append(update[key])
                break
    if not messages:
        raise RuntimeError(
            "No chat was found. Open your bot in Telegram, tap Start, send Hej, then run this command again."
        )
    chat = messages[-1]["chat"]
    label = (
        chat.get("username")
        or " ".join(part for part in (chat.get("first_name"), chat.get("last_name")) if part)
        or str(chat["id"])
    )
    return str(chat["id"]), label


def _set_secret(name: str, value: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", name],
        input=value,
        text=True,
        check=True,
    )


def main() -> int:
    token = getpass.getpass("Paste the complete BotFather token (hidden): ").strip()
    if not TOKEN_PATTERN.fullmatch(token):
        print("ERROR: That does not look like a complete Telegram bot token.")
        return 2
    try:
        chat_id, chat_label = _latest_chat(token)
        print(f"Found Telegram chat: {chat_label} ({chat_id})")
        _set_secret("TELEGRAM_BOT_TOKEN", token)
        _set_secret("TELEGRAM_CHAT_ID", chat_id)
        subprocess.run(
            ["gh", "workflow", "run", "generate-morgonkoll.yml"],
            check=True,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}")
        return 2
    finally:
        token = ""

    print("Secrets saved with non-empty values and a new delivery test was started.")
    print("Run `gh run watch` to follow it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

