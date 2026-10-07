import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { consultar } from "./api";
import { Comparador } from "./Comparador";
import { Mapa } from "./Mapa";
import { CAR_RE, type Alerta, type Linha, type Resultado } from "./types";

function formatarData(valor: string | null | undefined): string {
  if (!valor) return "—";
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleDateString("pt-BR");
}

function formatarHa(valor: number | null | undefined): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

function formatarProb(valor: number | null | undefined): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return `${(valor * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function linhasDe(resultados: Resultado[]): Linha[] {
  const linhas: Linha[] = [];
  for (const resultado of resultados) {
    if (resultado.alertas.length === 0) {
      linhas.push({
        key: `${resultado.car_code}:imovel`,
        resultado,
        alerta: null,
      });
      continue;
    }
    resultado.alertas.forEach((alerta, index) => {
      linhas.push({
        key: `${resultado.car_code}:${alerta.alert_code ?? index}`,
        resultado,
        alerta,
      });
    });
  }
  return linhas.sort((a, b) => (b.alerta?.proba_alta ?? -1) - (a.alerta?.proba_alta ?? -1));
}

export function App() {
  const [rascunho, setRascunho] = useState("");
  const [codigos, setCodigos] = useState<string[]>([]);
  const [avisoForm, setAvisoForm] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [resultados, setResultados] = useState<Resultado[]>([]);
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [mapaCheio, setMapaCheio] = useState(false);
  const painelMapa = useRef<HTMLElement>(null);

  useEffect(() => {
    const aoSair = () => {
      if (!document.fullscreenElement) setMapaCheio(false);
      window.dispatchEvent(new Event("resize"));
    };
    document.addEventListener("fullscreenchange", aoSair);
    return () => document.removeEventListener("fullscreenchange", aoSair);
  }, []);

  const linhas = useMemo(() => linhasDe(resultados), [resultados]);
  const linha = linhas.find((item) => item.key === selecionada) ?? null;

  function adicionar(event?: FormEvent) {
    event?.preventDefault();
    const partes = rascunho
      .split(/[\s,;]+/)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
    if (partes.length === 0) return;
    const invalidos = partes.filter((code) => !CAR_RE.test(code));
    const validos = partes.filter((code) => CAR_RE.test(code) && !codigos.includes(code));
    setCodigos((atual) => [...atual, ...validos]);
    setRascunho("");
    setAvisoForm(
      invalidos.length
        ? "Use o formato UF-0000000-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX."
        : null,
    );
  }

  async function consultarCodigos() {
    if (codigos.length === 0) {
      setAvisoForm("Inclua ao menos um código CAR.");
      return;
    }
    setCarregando(true);
    setErro(null);
    setAvisoForm(null);
    try {
      const data = await consultar(codigos);
      setResultados(data);
      const primeiras = linhasDe(data);
      setSelecionada(primeiras[0]?.key ?? null);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível consultar.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="pagina">
      <header className="topo">
        <div>
          <p className="olho">Fiscalização ambiental</p>
          <h1>Priorização de alertas</h1>
        </div>
        <p className="resumo">
          Informe o CAR. O imóvel entra no mapa, os alertas do MapBiomas recebem prioridade do
          modelo e as imagens de antes e depois aparecem abaixo.
        </p>
      </header>

      <section className="entrada">
        <form onSubmit={adicionar}>
          <label htmlFor="car">Código CAR</label>
          <div className="linha-form">
            <input
              id="car"
              value={rascunho}
              onChange={(event) => setRascunho(event.target.value)}
              placeholder="AC-1200708-19C3C6A0A7B6488096185809637AC4AF"
              autoComplete="off"
              spellCheck={false}
            />
            <button type="submit" className="secundario">
              Incluir
            </button>
            <button type="button" onClick={consultarCodigos} disabled={carregando}>
              {carregando ? "Consultando…" : "Consultar"}
            </button>
          </div>
        </form>
        {avisoForm && <p className="aviso">{avisoForm}</p>}
        {codigos.length > 0 && (
          <ul className="chips">
            {codigos.map((code) => (
              <li key={code}>
                <code>{code}</code>
                <button
                  type="button"
                  aria-label={`Remover ${code}`}
                  onClick={() => setCodigos((atual) => atual.filter((item) => item !== code))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {erro && <p className="erro">{erro}</p>}
      </section>

      <div className="workspace">
        <section className="painel tabela-painel" aria-label="Alertas priorizados">
          <header>
            <h2>Alertas</h2>
            <p>{linhas.length ? `${linhas.length} linha(s), maior probabilidade de alta primeiro` : "Nenhuma consulta ainda"}</p>
          </header>
          <div className="tabela-scroll">
            <table>
              <thead>
                <tr>
                  <th>CAR</th>
                  <th>Alerta</th>
                  <th>Município</th>
                  <th>Área (ha)</th>
                  <th>Fonte</th>
                  <th>Data</th>
                  <th>Prioridade</th>
                  <th>P(alta)</th>
                  <th>P(média)</th>
                  <th>P(baixa)</th>
                </tr>
              </thead>
              <tbody>
                {linhas.length === 0 && (
                  <tr>
                    <td colSpan={10} className="vazio">
                      Inclua um CAR e consulte para ver a prioridade.
                    </td>
                  </tr>
                )}
                {linhas.map((item) => (
                  <LinhaTabela
                    key={item.key}
                    linha={item}
                    ativa={item.key === selecionada}
                    onSelect={() => setSelecionada(item.key)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section
          className={`painel mapa-painel${mapaCheio ? " mapa-expandido" : ""}`}
          aria-label="Mapa do imóvel"
          ref={painelMapa}
        >
          <header>
            <h2>Mapa</h2>
            <button
              type="button"
              className="secundario tela-cheia"
              onClick={() => {
                const painel = painelMapa.current;
                if (!painel) return;
                const aberto = document.fullscreenElement === painel || mapaCheio;
                if (aberto) {
                  if (document.fullscreenElement) void document.exitFullscreen();
                  setMapaCheio(false);
                } else {
                  void painel.requestFullscreen().catch(() => setMapaCheio(true));
                }
                requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
              }}
            >
              {mapaCheio ? "Fechar" : "Tela cheia"}
            </button>
          </header>
          <Mapa linhas={linhas} selecionada={selecionada} onSelect={setSelecionada} />
          <ul className="legenda">
            <li><i className="alta" /> Alta</li>
            <li><i className="media" /> Média</li>
            <li><i className="baixa" /> Baixa</li>
          </ul>
        </section>
      </div>

      <section className="imagens" aria-label="Antes e depois">
        <header>
          <h2>Antes e depois</h2>
          <p>
            {linha?.alerta
              ? `${linha.resultado.car_code} · alerta ${linha.alerta.alert_code ?? "—"}`
              : "Selecione um alerta na tabela"}
          </p>
        </header>
        {linha?.resultado.erro && <p className="erro">{linha.resultado.erro}</p>}
        {linha?.resultado.aviso && <p className="aviso">{linha.resultado.aviso}</p>}
        {linha?.resultado.condicao && (
          <p className="condicao">
            {linha.resultado.municipio ? `${linha.resultado.municipio} · ` : ""}
            {linha.resultado.condicao}
          </p>
        )}
        <Comparador
          antes={linha?.alerta?.imagem_antes ?? null}
          depois={linha?.alerta?.imagem_depois ?? null}
        />
      </section>
    </div>
  );
}

function LinhaTabela({
  linha,
  ativa,
  onSelect,
}: {
  linha: Linha;
  ativa: boolean;
  onSelect: () => void;
}) {
  const alerta: Alerta | null = linha.alerta;
  return (
    <tr className={ativa ? "ativa" : undefined} onClick={onSelect}>
      <td>
        <code>{linha.resultado.car_code}</code>
      </td>
      <td>{alerta?.alert_code ?? "—"}</td>
      <td>{linha.resultado.municipio ?? "—"}</td>
      <td>{formatarHa(alerta?.area_alerta_ha ?? linha.resultado.area_imovel_ha)}</td>
      <td>{alerta ? alerta.fonte.replaceAll("|", ", ") : "—"}</td>
      <td>{formatarData(alerta?.detected_at)}</td>
      <td>
        {alerta ? (
          <span className={`selo ${alerta.prioridade}`}>{alerta.prioridade}</span>
        ) : (
          <span className="selo neutro">sem alerta</span>
        )}
      </td>
      <td>{formatarProb(alerta?.proba_alta)}</td>
      <td>{formatarProb(alerta?.proba_media)}</td>
      <td>{formatarProb(alerta?.proba_baixa)}</td>
    </tr>
  );
}
