"""Monta as features do modelo a partir de SiCAR e MapBiomas Alerta."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "area_alerta_ha",
    "area_imovel_ha",
    "modulos_fiscais",
    "fracao_imovel",
    "recencia_dias",
    "n_alertas_imovel",
    "status_alerta",
    "fonte_alerta",
    "status_imovel",
    "condicao",
    "tipo_imovel",
    "uf",
]

DESCONHECIDO = "desconhecido"


def sources_as_text(value) -> str:
    """Junta as fontes do alerta no mesmo formato do treino (``A|B``)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return DESCONHECIDO
    if isinstance(value, (list, tuple, set)):
        parts = sorted(str(item).strip() for item in value if item is not None and str(item).strip())
        return "|".join(parts) or DESCONHECIDO
    text = str(value).strip()
    return text or DESCONHECIDO


def _as_text(value, default: str = DESCONHECIDO) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    text = str(value).strip()
    return text or default


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _recencia_dias(detected_at) -> float | None:
    detected = _parse_datetime(detected_at)
    if detected is None:
        return None
    delta = datetime.now(timezone.utc) - detected
    return max(0.0, delta.total_seconds() / 86400.0)


def build_feature_frame(
    alerts: list[dict],
    *,
    area_imovel_ha,
    modulos_fiscais,
    status_imovel,
    condicao,
    tipo_imovel,
    uf: str,
) -> pd.DataFrame:
    """Uma linha por alerta, com os nomes esperados pelo pipeline treinado."""
    n_alertas = len(alerts) or 1
    area_imovel = pd.to_numeric(area_imovel_ha, errors="coerce")
    modulos = pd.to_numeric(modulos_fiscais, errors="coerce")
    rows = []
    for alert in alerts:
        area_alerta = pd.to_numeric(alert.get("areaHa"), errors="coerce")
        if pd.notna(area_imovel) and float(area_imovel) != 0 and pd.notna(area_alerta):
            fracao = float(area_alerta) / float(area_imovel)
        else:
            fracao = np.nan
        detected = alert.get("detectedAt") or alert.get("publishedAt")
        rows.append(
            {
                "area_alerta_ha": area_alerta,
                "area_imovel_ha": area_imovel,
                "modulos_fiscais": modulos,
                "fracao_imovel": fracao,
                "recencia_dias": _recencia_dias(detected),
                "n_alertas_imovel": n_alertas,
                "status_alerta": _as_text(alert.get("statusName")),
                "fonte_alerta": sources_as_text(alert.get("sources")),
                "status_imovel": _as_text(status_imovel),
                "condicao": _as_text(condicao),
                "tipo_imovel": _as_text(tipo_imovel),
                "uf": _as_text(uf).upper(),
            }
        )
    frame = pd.DataFrame(rows)
    return frame[FEATURE_NAMES]
