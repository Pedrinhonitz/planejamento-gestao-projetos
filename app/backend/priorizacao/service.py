"""Consulta SiCAR e MapBiomas e devolve o imóvel priorizado."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import transform

from hooks.http_sicar_hook import HttpSicarHook
from priorizacao.features import build_feature_frame
from priorizacao.imagens import escolher_antes_depois
from priorizacao.predict import prever

logger = logging.getLogger(__name__)


def credenciais_mapbiomas() -> tuple[str, str] | None:
    """Lê usuário e senha do ambiente. Não registra os valores."""
    username = os.getenv("MAPBIOMAS_USERNAME", "").strip()
    password = os.getenv("MAPBIOMAS_PASSWORD", "").strip()
    if not username or not password:
        return None
    return username, password


def _numero(value):
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return float(number)


def _texto(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _bounds_trocados(minx: float, miny: float, maxx: float, maxy: float) -> bool:
    """GeoServer às vezes devolve latitude, longitude. O Brasil cabe neste teste."""
    return -40 <= minx <= 10 and -40 <= maxx <= 10 and -80 <= miny <= -30 and -80 <= maxy <= -30


def geometria_geojson(geometry) -> dict | None:
    """Normaliza a geometria do SiCAR para GeoJSON em longitude, latitude."""
    if not geometry:
        return None
    try:
        geom = shape(geometry)
    except Exception:
        logger.warning("Geometria do SiCAR inválida.")
        return None
    if geom.is_empty:
        return None
    minx, miny, maxx, maxy = geom.bounds
    if _bounds_trocados(minx, miny, maxx, maxy):
        geom = transform(lambda x, y, z=None: (y, x), geom)
    return mapping(geom)


def _bbox(alert: dict) -> list[list[float]] | None:
    box = alert.get("boundingBox") or {}
    if not isinstance(box, dict):
        return None
    try:
        return [
            [float(box["swLng"]), float(box["swLat"])],
            [float(box["neLng"]), float(box["neLat"])],
        ]
    except (KeyError, TypeError, ValueError):
        return None


def _ponto(alert: dict) -> list[float] | None:
    coords = alert.get("coordenates") or {}
    if not isinstance(coords, dict):
        return None
    try:
        return [float(coords["longitude"]), float(coords["latitude"])]
    except (KeyError, TypeError, ValueError):
        return None


def _mensagem_publica(exc: Exception) -> str:
    text = str(exc).lower()
    if any(piece in text for piece in ("autenticação", "token", "sign in", "senha", "usuário", "usuario")):
        return "Falha na autenticação com o MapBiomas Alerta. Confira usuário e senha no ambiente do servidor."
    if "timeout" in text or "conexão" in text or "connection" in text:
        return "O serviço externo não respondeu a tempo. Tente de novo em instantes."
    return "Não foi possível obter os alertas deste CAR."


def _base(
    car_code: str,
    *,
    props: dict | None = None,
    rural: dict | None = None,
    geometry=None,
    aviso: str | None = None,
    erro: str | None = None,
) -> dict:
    props = props or {}
    rural = rural or {}
    uf = _texto(props.get("uf")) or _texto(rural.get("stateAcronym")) or car_code[:2].upper()
    area = _numero(props.get("area"))
    if area is None:
        area = _numero(rural.get("areaHa"))
    return {
        "car_code": car_code,
        "municipio": _texto(props.get("municipio")),
        "uf": uf.upper(),
        "status_imovel": _texto(props.get("status_imovel")),
        "condicao": _texto(props.get("condicao")),
        "tipo_imovel": _texto(props.get("tipo_imovel")),
        "area_imovel_ha": area,
        "modulos_fiscais": _numero(props.get("m_fiscal")),
        "geometry": geometry,
        "aviso": aviso,
        "erro": erro,
        "alertas": [],
    }


def consultar_um(car_code: str, mapbiomas_hook) -> dict:
    """Cruza um CAR, prediz a prioridade de cada alerta e anexa geometria e imagens."""
    imovel = None
    aviso_sicar = None
    try:
        imovel = HttpSicarHook().get_imovel_by_code(car_code)
    except Exception:
        logger.exception("Falha ao consultar o SiCAR para %s", car_code)
        aviso_sicar = "Não foi possível consultar o SiCAR. O mapa usa o recorte do alerta, se houver."

    props = (imovel or {}).get("properties") or {}
    geometry = geometria_geojson((imovel or {}).get("geometry"))

    try:
        cruzamento = mapbiomas_hook.get_alerts_by_car(car_code)
    except Exception as exc:
        logger.exception("Falha ao consultar o MapBiomas para %s", car_code)
        if imovel is None:
            return _base(car_code, erro="Não foi possível consultar SiCAR nem MapBiomas para este CAR.")
        return _base(car_code, props=props, geometry=geometry, aviso=aviso_sicar, erro=_mensagem_publica(exc))

    rural = cruzamento.get("property") or {}
    alerts = list(cruzamento.get("alerts") or [])
    resultado = _base(car_code, props=props, rural=rural, geometry=geometry, aviso=aviso_sicar)

    if not alerts:
        if not resultado["aviso"]:
            resultado["aviso"] = "Nenhum alerta do MapBiomas vinculado a este CAR."
        return resultado

    frame = build_feature_frame(
        alerts,
        area_imovel_ha=resultado["area_imovel_ha"],
        modulos_fiscais=props.get("m_fiscal"),
        status_imovel=props.get("status_imovel"),
        condicao=props.get("condicao"),
        tipo_imovel=props.get("tipo_imovel"),
        uf=resultado["uf"],
    )
    frame.insert(0, "origem", range(len(frame)))
    scored = prever(frame)

    for _, row in scored.iterrows():
        alert = alerts[int(row["origem"])]
        antes, depois = escolher_antes_depois(alert)
        detected = alert.get("detectedAt") or alert.get("publishedAt")
        resultado["alertas"].append(
            {
                "alert_code": _texto(alert.get("alertCode")),
                "area_alerta_ha": _numero(row["area_alerta_ha"]),
                "detected_at": str(detected) if detected else None,
                "published_at": str(alert.get("publishedAt")) if alert.get("publishedAt") else None,
                "fonte": _texto(row["fonte_alerta"]) or "desconhecido",
                "status_alerta": _texto(row["status_alerta"]) or "desconhecido",
                "prioridade": str(row["prioridade"]),
                "proba_alta": _numero(row.get("proba_alta")),
                "proba_media": _numero(row.get("proba_media")),
                "proba_baixa": _numero(row.get("proba_baixa")),
                "bbox": _bbox(alert),
                "ponto": _ponto(alert),
                "imagem_antes": antes,
                "imagem_depois": depois,
            }
        )
    return resultado


def consultar_varios(car_codes: list[str], mapbiomas_hook) -> list[dict]:
    """Consulta vários CARs em paralelo e devolve na ordem pedida."""
    if not car_codes:
        return []
    resultados: list[dict | None] = [None] * len(car_codes)
    workers = min(4, len(car_codes))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {
            pool.submit(consultar_um, code, mapbiomas_hook): index
            for index, code in enumerate(car_codes)
        }
        for futuro in as_completed(futuros):
            index = futuros[futuro]
            code = car_codes[index]
            try:
                resultados[index] = futuro.result()
            except Exception:
                logger.exception("Falha inesperada ao consultar %s", code)
                resultados[index] = _base(code, erro="Não foi possível priorizar este CAR.")
    return [item for item in resultados if item is not None]
