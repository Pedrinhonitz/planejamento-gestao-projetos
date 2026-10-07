"""Carrega o joblib e aplica o mesmo ``prever`` do notebook de uso."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from priorizacao.features import FEATURE_NAMES


class ModeloAusente(FileNotFoundError):
    """O arquivo do modelo não está no caminho configurado."""


def model_path() -> Path:
    """Resolve o joblib via ``MODEL_PATH`` ou sobe a árvore até ``notebooks/output``."""
    configured = os.getenv("MODEL_PATH")
    if configured:
        return Path(configured)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "notebooks" / "output" / "modelo_priorizacao_alertas.joblib"
        if candidate.exists():
            return candidate
    raise ModeloAusente(
        "Modelo não encontrado. Defina MODEL_PATH para modelo_priorizacao_alertas.joblib."
    )


@lru_cache(maxsize=1)
def load_artifact():
    """Carrega pipeline, nomes de features e classes."""
    path = model_path()
    if not path.exists():
        raise ModeloAusente(f"Modelo não encontrado em {path}.")
    artifact = joblib.load(path)
    missing = [name for name in FEATURE_NAMES if name not in artifact.get("feature_names", [])]
    if missing or "pipeline" not in artifact:
        raise ModeloAusente("O arquivo do modelo não tem pipeline e feature_names esperados.")
    return artifact


def prever(frame: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta prioridade e probabilidades, ordenando por ``proba_alta``."""
    artifact = load_artifact()
    pipe = artifact["pipeline"]
    features = list(artifact["feature_names"])
    proba = pipe.predict_proba(frame[features])
    classes = list(pipe.classes_)
    out = frame.copy()
    out["prioridade"] = pipe.predict(frame[features])
    for index, label in enumerate(classes):
        out[f"proba_{label}"] = proba[:, index]
    if "alta" in classes:
        out = out.sort_values("proba_alta", ascending=False)
    return out.reset_index(drop=True)
