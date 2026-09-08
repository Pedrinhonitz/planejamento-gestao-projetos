"""Pipeline MVP de priorização de alertas de desmatamento (MapBiomas + CAR).

Uso:
    python -m ml.pipeline ingest --car-code UF-0000000-XXXXXXXX
    python -m ml.pipeline train --sample
    python -m ml.pipeline rank --sample --top 10
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

MODEL_VERSION = "0.1.0"
SEED = 42

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data/raw/alerts.csv"
MODEL_PATH = ROOT / "data/models/priorizacao.joblib"
METADATA_PATH = ROOT / "data/models/priorizacao_metadata.json"
RANKED_PATH = ROOT / "data/processed/alertas_priorizados.csv"

# Atributos do modelo e sua descrição legível, usada na explicação do ranking (US-06).
FEATURES = {
    "area_ha": "área desmatada do alerta (ha)",
    "property_area_ha": "área total do imóvel (ha)",
    "area_ratio": "proporção do imóvel atingida",
    "days_since_detection": "dias desde a detecção",
    "alerts_in_property": "alertas no mesmo imóvel",
    "overlaps_uc": "sobreposição com Unidade de Conservação",
    "overlaps_ti": "sobreposição com Terra Indígena",
    "is_embargoed": "imóvel em área embargada",
}

# Resultado real da fiscalização (US-09); na falta dele o treino usa rótulo fraco.
OUTCOME_COLUMN = "resultado_fiscalizacao"
POSITIVE_OUTCOMES = ("autuacao", "embargo")
WEAK_WEIGHTS = {"overlaps_ti": 1.5, "is_embargoed": 1.2, "overlaps_uc": 1.0, "area_ratio": 1.0}

SOURCES = ["MapBiomas Alerta v2", "SiCAR / GeoServer CAR"]


def load_alerts(path=RAW_PATH, sample=False):
    """Carrega o CSV bruto de alertas ou gera a amostra sintética."""
    if sample:
        return sample_alerts()
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Conjunto bruto não encontrado em {path}. Rode `ingest` ou use `--sample`."
        )
    return pd.read_csv(path)


def sample_alerts(n_rows=800, seed=SEED):
    """Gera alertas sintéticos para rodar o pipeline sem credenciais (não são dados reais)."""
    rng = np.random.default_rng(seed)
    n_properties = max(1, n_rows // 3)
    properties = rng.integers(0, n_properties, size=n_rows)
    areas = rng.lognormal(3.6, 0.9, n_properties).round(2)
    cities = rng.choice(["Chapecó", "Xanxerê", "São Miguel do Oeste", "Curitibanos", "Lages"], n_properties)
    return pd.DataFrame({
        "alert_code": [f"MB-{i:06d}" for i in range(n_rows)],
        "car_code": [f"SC-42000{p:02d}-SINTETICO{p:06d}" for p in properties],
        "municipality": cities[properties],
        "state": "SC",
        "area_ha": rng.lognormal(1.0, 1.1, n_rows).round(2),
        "property_area_ha": areas[properties],
        "detected_at": pd.Timestamp.today().normalize()
        - pd.to_timedelta(rng.integers(1, 365, n_rows), unit="D"),
        "overlaps_uc": rng.random(n_rows) < 0.12,
        "overlaps_ti": rng.random(n_rows) < 0.06,
        "is_embargoed": rng.random(n_rows) < 0.15,
    })


def build_features(df):
    """Monta a matriz de atributos do modelo a partir do conjunto bruto."""
    area = pd.to_numeric(df["area_ha"], errors="coerce").fillna(0.0)
    property_area = pd.to_numeric(df["property_area_ha"], errors="coerce")
    detected = pd.to_datetime(df["detected_at"], errors="coerce", utc=True)

    x = pd.DataFrame(index=df.index)
    x["area_ha"] = area
    x["property_area_ha"] = property_area.fillna(0.0)
    x["area_ratio"] = (
        (area / property_area).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(0, 1)
    )
    x["days_since_detection"] = (
        (pd.Timestamp.now(tz="UTC").normalize() - detected).dt.days.fillna(0).clip(lower=0)
    )
    x["alerts_in_property"] = df.groupby("car_code")["car_code"].transform("size").fillna(1)
    for layer in ("overlaps_uc", "overlaps_ti", "is_embargoed"):
        x[layer] = _to_binary(df.get(layer))
    return x[list(FEATURES)].astype(float)


def build_label(df, x):
    """Alvo do treino: resultado de campo (US-09) ou, na falta dele, rótulo fraco por regras."""
    if OUTCOME_COLUMN in df.columns and df[OUTCOME_COLUMN].notna().any():
        outcome = df[OUTCOME_COLUMN].astype("string").str.strip().str.lower()
        info = {"tipo": "resultado_de_campo", "coluna": OUTCOME_COLUMN}
        return outcome.isin(POSITIVE_OUTCOMES).astype(int), info

    # Bootstrap do MVP: pontua gravidade legal e marca os 30% do topo como positivos.
    severity = np.log1p(x["area_ha"]) / np.log1p(x["area_ha"]).max()
    for column, weight in WEAK_WEIGHTS.items():
        severity = severity + weight * x[column] / (x[column].max() or 1)
    severity = severity + np.random.default_rng(SEED).normal(0, 0.15, len(x))
    info = {
        "tipo": "rotulo_fraco",
        "pesos": WEAK_WEIGHTS,
        "descricao": "Regras de gravidade legal; substituir pelos resultados de campo da US-09.",
    }
    return (severity > severity.quantile(0.7)).astype(int), info


def train(x, y, seed=SEED):
    """Treina o classificador e mede o desempenho na partição de teste."""
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=seed, stratify=y if y.nunique() > 1 else None
    )
    model = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=5,
        class_weight="balanced", random_state=seed, n_jobs=-1,
    )
    model.fit(x_train, y_train)

    scores = model.predict_proba(x_test)[:, 1]
    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, scores)), 4),
        "average_precision": round(float(average_precision_score(y_test, scores)), 4),
        "n_treino": len(x_train),
        "n_teste": len(x_test),
        "taxa_positivos": round(float(y.mean()), 4),
    }
    return model, metrics


def rank(df, x, bundle, top=None):
    """Pontua de 0 a 100, ordena e explica os fatores de cada alerta (US-01, US-06)."""
    model, stats = bundle["model"], bundle["feature_stats"]
    scores = model.predict_proba(x)[:, 1]
    # Explicação aproximada: importância global do atributo x desvio da mediana do treino.
    contributions = (x - stats["mediana"]) / stats["desvio"] * model.feature_importances_

    context = ["alert_code", "car_code", "municipality", "state", "detected_at", "area_ha"]
    ranked = df[[c for c in context if c in df.columns]].copy()
    ranked["prioridade"] = (scores * 100).round(1)
    ranked["fatores"] = [_explain(x.iloc[i], contributions.iloc[i]) for i in range(len(x))]
    ranked["versao_modelo"] = MODEL_VERSION
    ranked["gerado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    ranked = ranked.sort_values("prioridade", ascending=False).reset_index(drop=True)
    ranked.insert(0, "posicao", np.arange(1, len(ranked) + 1))
    return ranked.head(top) if top else ranked


def save_model(model, x, metrics, label_info):
    """Salva o modelo e a trilha de auditoria da versão treinada (US-07)."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    stats = pd.DataFrame({"mediana": x.median(), "desvio": x.std().replace(0.0, 1.0).fillna(1.0)})
    joblib.dump({"model": model, "feature_stats": stats}, MODEL_PATH)

    metadata = {
        "versao_modelo": MODEL_VERSION,
        "treinado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_git": _git_commit(),
        "algoritmo": type(model).__name__,
        "semente": SEED,
        "n_amostras": len(x),
        "rotulo": label_info,
        "metricas": metrics,
        "fontes_de_dados": SOURCES,
        "importancias": {
            name: round(float(value), 4)
            for name, value in zip(FEATURES, model.feature_importances_)
        },
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def load_bundle():
    """Carrega o modelo treinado e as estatísticas usadas na explicação."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Modelo não encontrado em {MODEL_PATH}. Rode `python -m ml.pipeline train`."
        )
    return joblib.load(MODEL_PATH)


def ingest(car_codes, username, password):
    """Coleta na API MapBiomas os alertas vinculados a cada código CAR."""
    sys.path.insert(0, str(ROOT / "notebooks"))
    from hooks.http_mapbiomas_alerts_hook import HttpMapbiomasAlertsHook

    hook = HttpMapbiomasAlertsHook(username=username, password=password)
    records = []
    for car_code in car_codes:
        result = hook.get_alerts_by_car(car_code)
        rural_property = result.get("property") or {}
        for alert in result.get("alerts") or []:
            records.append({
                "alert_code": alert.get("alertCode"),
                "car_code": rural_property.get("propertyCode") or car_code,
                # Município e camadas UC/TI/embargo dependem do cruzamento com o
                # SiCAR, ainda não implementado (US-02, US-04, US-11).
                "municipality": None,
                "state": rural_property.get("state"),
                "area_ha": alert.get("areaHa"),
                "property_area_ha": rural_property.get("areaHa"),
                "detected_at": alert.get("detectedAt"),
                "overlaps_uc": None,
                "overlaps_ti": None,
                "is_embargoed": None,
            })
    return pd.DataFrame(records)


def _to_binary(values):
    """Normaliza coluna booleana/textual para 0 ou 1; camada ausente vira 0."""
    if values is None:
        return 0
    if values.dtype == object or isinstance(values.dtype, pd.StringDtype):
        normalized = values.astype("string").str.strip().str.lower()
        return normalized.isin(["true", "1", "sim"]).astype(int)
    return values.fillna(0).astype(bool).astype(int)


def _explain(values, contribution):
    """Descreve os três atributos que mais elevaram a prioridade do alerta."""
    top = contribution[contribution > 0].sort_values(ascending=False).head(3)
    if top.empty:
        return "sem fator acima da mediana do treino"
    return "; ".join(f"{FEATURES[name]}: {values[name]:g}" for name in top.index)


def _git_commit():
    """Hash curto do commit atual, para a trilha de auditoria."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def cmd_ingest(args):
    """Coleta os alertas e grava o conjunto bruto."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    username, password = os.getenv("MAPBIOMAS_USERNAME"), os.getenv("MAPBIOMAS_PASSWORD")
    if not (username and password):
        print("Defina MAPBIOMAS_USERNAME e MAPBIOMAS_PASSWORD (veja notebooks/.env.example).", file=sys.stderr)
        return 1

    df = ingest(args.car_code, username, password)
    if df.empty:
        print("Nenhum alerta encontrado para os códigos CAR informados.")
        return 0
    _write_csv(df, args.output)
    print(f"{len(df)} alertas gravados em {args.output}")
    return 0


def cmd_train(args):
    """Treina o modelo e grava modelo e metadados."""
    df = load_alerts(args.input, sample=args.sample)
    x = build_features(df)
    y, label_info = build_label(df, x)
    if y.nunique() < 2:
        print("Rótulo com uma única classe; não é possível treinar.", file=sys.stderr)
        return 1

    model, metrics = train(x, y)
    save_model(model, x, metrics, label_info)
    print(f"Modelo treinado com {len(df)} alertas (rótulo: {label_info['tipo']}).")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


def cmd_rank(args):
    """Pontua os alertas e grava a lista priorizada."""
    df = load_alerts(args.input, sample=args.sample)
    ranked = rank(df, build_features(df), load_bundle(), top=args.top)
    _write_csv(ranked, args.output)
    print(ranked.head(args.top or 10).to_string(index=False))
    print(f"\n{len(ranked)} alertas priorizados gravados em {args.output}")
    return 0


def _write_csv(df, path):
    """Grava o DataFrame criando o diretório de destino se preciso."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main(argv=None):
    """Interpreta a linha de comando e executa o subcomando escolhido."""
    parser = argparse.ArgumentParser(
        prog="python -m ml.pipeline",
        description="Priorização de alertas de crimes ambientais.",
    )
    sub = parser.add_subparsers(required=True)

    ingest_cmd = sub.add_parser("ingest", help="coleta alertas na API MapBiomas")
    ingest_cmd.add_argument("--car-code", action="append", required=True, help="código CAR (pode repetir)")
    ingest_cmd.add_argument("--output", type=Path, default=RAW_PATH)
    ingest_cmd.set_defaults(handler=cmd_ingest)

    train_cmd = sub.add_parser("train", help="treina o modelo de priorização")
    train_cmd.set_defaults(handler=cmd_train)

    rank_cmd = sub.add_parser("rank", help="gera a lista priorizada")
    rank_cmd.add_argument("--top", type=int, help="quantidade de alertas retornados")
    rank_cmd.add_argument("--output", type=Path, default=RANKED_PATH)
    rank_cmd.set_defaults(handler=cmd_rank)

    for command in (train_cmd, rank_cmd):
        command.add_argument("--input", type=Path, default=RAW_PATH)
        command.add_argument("--sample", action="store_true", help="usa a amostra sintética")

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
