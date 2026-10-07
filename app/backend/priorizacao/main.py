"""API HTTP da priorização de alertas por código CAR."""

from __future__ import annotations

import logging
import re
import sys
import warnings
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _ensure_hooks_path() -> None:
    """Inclui ``notebooks/`` no path para reutilizar os hooks existentes."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        hooks = parent / "notebooks" / "hooks"
        if hooks.is_dir():
            notebooks = str(hooks.parent)
            if notebooks not in sys.path:
                sys.path.insert(0, notebooks)
            return


_ensure_hooks_path()

from hooks.http_mapbiomas_alerts_hook import HttpMapbiomasAlertsHook  # noqa: E402
from priorizacao.imagens import host_da_plataforma, imagem_permitida  # noqa: E402
from priorizacao.predict import ModeloAusente, load_artifact  # noqa: E402
from priorizacao.service import (  # noqa: E402
    consultar_varios,
    credenciais_mapbiomas,
)

CAR_RE = re.compile(r"^[A-Z]{2}-\d{7}-[A-F0-9]{32}$")

app = FastAPI(title="Priorização de alertas", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

try:
    from dotenv import load_dotenv

    for parent in Path(__file__).resolve().parents:
        for candidate in (parent / "notebooks" / ".env", parent / ".env"):
            if candidate.is_file():
                load_dotenv(candidate)
                break
        else:
            continue
        break
except ImportError:
    pass


class ConsultaRequest(BaseModel):
    car_codes: list[str] = Field(min_length=1, max_length=20)


def _normalizar(codes: list[str]) -> tuple[list[str], list[dict]]:
    vistos: set[str] = set()
    validos: list[str] = []
    invalidos: list[dict] = []
    for bruto in codes:
        code = bruto.strip().upper()
        if not code or code in vistos:
            continue
        vistos.add(code)
        if CAR_RE.fullmatch(code):
            validos.append(code)
        else:
            invalidos.append(
                {
                    "car_code": code,
                    "municipio": None,
                    "uf": None,
                    "status_imovel": None,
                    "condicao": None,
                    "tipo_imovel": None,
                    "area_imovel_ha": None,
                    "modulos_fiscais": None,
                    "geometry": None,
                    "aviso": None,
                    "erro": "Código CAR inválido. Use o formato UF-0000000-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.",
                    "alertas": [],
                }
            )
    return validos, invalidos


@app.get("/api/health")
def health():
    """Informa se o joblib está acessível. Não chama serviços externos."""
    try:
        artifact = load_artifact()
        classes = list(artifact["pipeline"].classes_)
    except ModeloAusente as exc:
        return {"ok": False, "detalhe": str(exc)}
    return {"ok": True, "classes": classes}


@app.post("/api/consultar")
def consultar(body: ConsultaRequest):
    """Prioriza os alertas dos CARs informados."""
    credenciais = credenciais_mapbiomas()
    if credenciais is None:
        raise HTTPException(
            status_code=503,
            detail="Defina MAPBIOMAS_USERNAME e MAPBIOMAS_PASSWORD no ambiente do servidor.",
        )
    validos, invalidos = _normalizar(body.car_codes)
    if not validos and invalidos:
        return {"resultados": invalidos}
    if not validos:
        raise HTTPException(status_code=422, detail="Informe ao menos um código CAR.")

    try:
        load_artifact()
    except ModeloAusente as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    username, password = credenciais
    hook = HttpMapbiomasAlertsHook(username=username, password=password)
    resultados = consultar_varios(validos, hook)
    return {"resultados": resultados + invalidos}


_mapbiomas_hook = None


def _token_plataforma() -> str | None:
    """Bearer só para baixar imagem hospedada na plataforma. Não registra a senha."""
    global _mapbiomas_hook
    credenciais = credenciais_mapbiomas()
    if credenciais is None:
        return None
    if _mapbiomas_hook is None:
        username, password = credenciais
        _mapbiomas_hook = HttpMapbiomasAlertsHook(username=username, password=password)
    return _mapbiomas_hook._ensure_token()


def _seguir_imagem(url: str) -> requests.Response:
    """Baixa a imagem seguindo no máximo três redirecionamentos em hosts permitidos."""
    atual = url
    for _ in range(3):
        if not imagem_permitida(atual):
            logger.info("Imagem recusada, host=%s", urlparse(atual).hostname)
            raise HTTPException(status_code=400, detail="Endereço de imagem não permitido.")
        headers = {"User-Agent": "priorizacao-alertas/1.0"}
        if host_da_plataforma(atual):
            token = _token_plataforma()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        response = requests.get(
            atual,
            timeout=60,
            allow_redirects=False,
            stream=True,
            headers=headers,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            destino = response.headers.get("Location")
            response.close()
            if not destino:
                raise HTTPException(status_code=502, detail="A imagem não pôde ser carregada.")
            atual = urljoin(atual, destino)
            continue
        return response
    raise HTTPException(status_code=502, detail="A imagem não pôde ser carregada.")


@app.get("/api/imagens")
def imagens(src: str = Query(min_length=8, max_length=8000)):
    """Encaminha uma imagem do MapBiomas para o browser."""
    if not imagem_permitida(src):
        logger.info("Imagem recusada, host=%s", urlparse(src).hostname)
        raise HTTPException(status_code=400, detail="Endereço de imagem não permitido.")
    response = _seguir_imagem(src)
    if response.status_code != 200:
        response.close()
        raise HTTPException(status_code=502, detail="A imagem não pôde ser carregada.")
    media = response.headers.get("Content-Type", "image/png")

    def chunks():
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            response.close()

    return StreamingResponse(chunks(), media_type=media.split(";")[0])
