<div align="center" id="top">
  <img src="./static/logo.jpg" alt="uffs-logo" style="width:300px; height:250px;" />

  &#xa0;

</div>

<h1 align="center">GCS817 — Planejamento e Gestão de Projetos</h1>

<p align="center">
  Ciência da Computação<br>
  Universidade Federal da Fronteira Sul (UFFS) · Campus Chapecó · 2026
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Google%20Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white" alt="Google Colab" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" />
</p>

<p align="center">
  <a href="#dart-sobre">Sobre</a> &#xa0; | &#xa0;
  <a href="#gear-configuração-de-ambiente">Ambiente</a> &#xa0; | &#xa0;
  <a href="#robot-pipeline-de-ml">Pipeline de ML</a> &#xa0; | &#xa0;
  <a href="#busts_in_silhouette-histórias-de-usuário">Histórias de usuário</a> &#xa0; | &#xa0;
  <a href="https://github.com/Pedrinhonitz" target="_blank">Autor</a>
</p>

<br>

## :dart: Sobre ##

Este trabalho da disciplina **GCS817 — Planejamento e Gestão de Projetos** aplica práticas de planejamento, execução e acompanhamento de sprints ao desenvolvimento de um sistema orientado a dados de **crimes ambientais**, utilizando alertas do [MapBiomas Alerts](https://alerta.mapbiomas.org/).

O objetivo é entregar incrementos a cada sprint (código, documentação e artigo científico), mantendo rastreabilidade das decisões e do progresso do projeto.

**Autor:** Bruno Schramm Vendruscolo e Pedro Henrique Klein

## :busts_in_silhouette: Histórias de usuário ##

As histórias de usuário do produto estão em [docs/historias-usuario.md](docs/historias-usuario.md).

## :gear: Configuração de ambiente ##

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

A ingestão via API MapBiomas exige credenciais. Copie `notebooks/.env.example` para
`.env` na raiz do repositório e preencha `MAPBIOMAS_USERNAME` e `MAPBIOMAS_PASSWORD`.

## :robot: Pipeline de ML ##

Pipeline MVP que ranqueia alertas de desmatamento por urgência e impacto ambiental
(US-01, US-06, US-07 e US-11). Ele roda em três comandos:

```bash
python -m ml.pipeline ingest --car-code UF-0000000-XXXXXXXX   # coleta alertas na API MapBiomas
python -m ml.pipeline train                                   # treina e versiona o modelo
python -m ml.pipeline rank --top 20                           # gera a lista priorizada
```

Para experimentar o fluxo ponta a ponta sem credenciais, use a amostra sintética:

```bash
python -m ml.pipeline train --sample && python -m ml.pipeline rank --sample --top 10
```

### Estrutura

Tudo vive em [`ml/pipeline.py`](ml/pipeline.py): coleta, atributos, treino
(`RandomForestClassifier`), ranking e linha de comando. Os artefatos ficam em
`data/`, fora do versionamento — `data/raw/alerts.csv`,
`data/models/priorizacao.joblib`, `data/models/priorizacao_metadata.json` e
`data/processed/alertas_priorizados.csv`.

### Atributos e explicabilidade

O modelo usa oito atributos: área do alerta, área do imóvel, proporção atingida,
dias desde a detecção, reincidência de alertas no imóvel e sobreposição com UC, TI
e embargo. Cada alerta da saída traz a coluna `fatores` com os três atributos que
mais elevaram sua prioridade (US-06).

O JSON de metadados registra versão do modelo, data/hora, commit, semente, fontes
de dados, atributos, métricas e importâncias — a trilha auditável exigida pela
US-07 e pela Portaria IBAMA nº 217/2023.

### Limitações desta versão

- **Rótulo fraco.** Ainda não existem resultados de fiscalização coletados (US-09),
  então o treino usa um alvo derivado de regras de gravidade legal. As métricas
  altas nesse cenário medem a reprodução das regras, não acerto em campo. Quando a
  coluna `resultado_fiscalizacao` aparece no conjunto bruto, o pipeline passa a
  usá-la automaticamente como rótulo real.
- **Camadas auxiliares.** As colunas de UC, TI e embargo existem no modelo, mas o
  `ingest` ainda não faz o cruzamento espacial — hoje elas só vêm preenchidas em
  conjuntos montados manualmente ou na amostra sintética.
- **Município.** A API de alertas não devolve o município; o campo depende do
  vínculo com o SiCAR (US-02/US-04), ainda não implementado no `ingest`.
- **Explicação aproximada.** Os `fatores` combinam a importância global do atributo
  com o desvio em relação à mediana do treino — uma aproximação de MVP, a ser
  trocada por atribuição exata (ex.: SHAP).

## :notebook: Notebooks ##

- `notebooks/` — testes de integração com as APIs SiCAR e MapBiomas Alerta.
- [`colab/`](colab/Planejamento_e_Gestão_de_Projetos_Analise_dos_Dados.ipynb) — análise
  dos dados no Colab: imóveis do SiCAR, alertas do MapBiomas e o ranking do pipeline.
  As credenciais vêm dos *Secrets* do Colab (`MAPBIOMAS_USERNAME`, `MAPBIOMAS_PASSWORD`).


Feito por <a href="https://github.com/Vendru" target="_blank">Vendru</a> e <a href="https://github.com/Pedrinhonitz" target="_blank">Pedrinhonitz</a>

&#xa0;

<a href="#top">Voltar ao topo</a>
