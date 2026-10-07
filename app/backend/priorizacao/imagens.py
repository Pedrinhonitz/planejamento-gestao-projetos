"""Escolhe as imagens de antes e depois e limita o proxy a hosts do MapBiomas."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import pandas as pd

ALLOWED_IMAGE_HOSTS = {
    "image.alerta.mapbiomas.org",
    "plataforma.alerta.mapbiomas.org",
    "alerta.mapbiomas.org",
    "storage.googleapis.com",
    "storage.cloud.google.com",
}

PLATFORM_HOSTS = {"plataforma.alerta.mapbiomas.org"}


def imagem_permitida(url: str) -> bool:
    """True só para HTTPS em hosts do MapBiomas ou do armazenamento público."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    if host in ALLOWED_IMAGE_HOSTS:
        return True
    return host.endswith(".mapbiomas.org") or host.endswith(".googleapis.com")


def host_da_plataforma(url: str) -> bool:
    """A plataforma do MapBiomas exige o Bearer; o CDN público de imagens não."""
    return (urlparse(url).hostname or "").lower() in PLATFORM_HOSTS


def proxy_path(url: str) -> str:
    """Caminho relativo que o browser pede ao próprio front."""
    return "/api/imagens?src=" + quote(url, safe="")


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _papel_pela_url(url: str) -> str | None:
    lowered = (url or "").lower()
    if "before" in lowered:
        return "antes"
    if "after" in lowered:
        return "depois"
    return None


def _as_imagem(image: dict | None) -> dict | None:
    if not image:
        return None
    url = image.get("url")
    if not url or not imagem_permitida(str(url)):
        return None
    acquired = image.get("acquiredAt")
    return {
        "url": proxy_path(str(url)),
        "acquired_at": str(acquired) if acquired else None,
        "satellite": image.get("satellite") or None,
    }


def _closest(images: list[dict], target: datetime | None) -> dict | None:
    if target is None or not images:
        return None
    dated = []
    for image in images:
        moment = _parse_datetime(image.get("acquiredAt"))
        if moment is not None:
            dated.append((abs((moment - target).total_seconds()), image))
    if not dated:
        return None
    dated.sort(key=lambda item: item[0])
    return dated[0][1]


def escolher_antes_depois(alert: dict) -> tuple[dict | None, dict | None]:
    """Par antes/depois a partir do nome do arquivo ou da data de aquisição."""
    images = [img for img in (alert.get("publishedImages") or []) if isinstance(img, dict) and img.get("url")]
    antes = next((img for img in images if _papel_pela_url(str(img.get("url"))) == "antes"), None)
    depois = next((img for img in images if _papel_pela_url(str(img.get("url"))) == "depois"), None)
    if antes or depois:
        return _as_imagem(antes), _as_imagem(depois)

    before_at = _parse_datetime(alert.get("imageAcquiredBeforeAt"))
    after_at = _parse_datetime(alert.get("imageAcquiredAfterAt"))
    if before_at or after_at:
        antes = _closest(images, before_at)
        restantes = [img for img in images if img is not antes]
        depois = _closest(restantes or images, after_at)
        if depois is antes:
            depois = _closest(restantes, after_at)
        return _as_imagem(antes), _as_imagem(depois)

    if len(images) >= 2:
        ordered = sorted(images, key=lambda img: str(img.get("acquiredAt") or ""))
        return _as_imagem(ordered[0]), _as_imagem(ordered[-1])
    if len(images) == 1:
        return _as_imagem(images[0]), None
    return None, None
