"""Send a verified Morgonkoll MP3 through Telegram's free Bot API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from .audio import verify_telegram_audio
from .errors import MorgonkollError


class TelegramDeliveryError(MorgonkollError):
    """Raised when Telegram rejects or cannot receive an episode."""


def _multipart(
    fields: Mapping[str, str],
    file_field: str,
    file_path: Path,
) -> Tuple[bytes, str]:
    boundary = f"morgonkoll-{uuid.uuid4().hex}"
    chunks: List[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def send_audio(
    audio_path: Path,
    bot_token: str,
    chat_id: str,
    caption: str,
    timeout_seconds: int = 120,
) -> int:
    if not bot_token.strip() or not chat_id.strip():
        raise TelegramDeliveryError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be configured"
        )
    verification = verify_telegram_audio(audio_path)
    title = str(verification["tags"]["title"])
    body, content_type = _multipart(
        {
            "chat_id": chat_id,
            "caption": caption,
            "title": title,
            "performer": "Morgonkoll",
        },
        file_field="audio",
        file_path=audio_path,
    )
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendAudio",
        data=body,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
            "User-Agent": "Morgonkoll/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TelegramDeliveryError(
            f"Telegram returned HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise TelegramDeliveryError(
            f"Could not reach Telegram: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise TelegramDeliveryError("Telegram returned an invalid response") from exc

    if payload.get("ok") is not True:
        raise TelegramDeliveryError(
            f"Telegram rejected the audio: {payload.get('description', 'unknown error')}"
        )
    try:
        return int(payload["result"]["message_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramDeliveryError(
            "Telegram accepted the request but returned no message id"
        ) from exc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument(
        "--caption",
        default="God morgon! Här kommer dagens Morgonkoll.",
    )
    args = parser.parse_args(argv)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    try:
        message_id = send_audio(
            args.audio,
            bot_token=token,
            chat_id=chat_id,
            caption=args.caption,
        )
    except TelegramDeliveryError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Telegram delivery succeeded (message id {message_id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

