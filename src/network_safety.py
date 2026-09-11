"""Network target validation shared by reviewed feed and article fetches."""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from typing import Iterable
from urllib.parse import urlparse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirect)


def host_allowed(hostname: str, allowed_hosts: Iterable[str]) -> bool:
    host = hostname.casefold().strip(".")
    return any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in allowed_hosts
    )


def validate_public_https_target(url: str, allowed_hosts: Iterable[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("network target must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise RuntimeError("network target contains disallowed URL authority fields")
    if not host_allowed(parsed.hostname, allowed_hosts):
        raise RuntimeError(f"network host is outside the reviewed allowlist: {parsed.hostname}")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RuntimeError(f"network host DNS lookup failed: {exc}") from exc
    for address in {item[4][0] for item in addresses}:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise RuntimeError(f"network host resolved to non-public address {ip}")

