import { useEffect, useState } from "react";
import type { Imagem } from "./types";

function formatarData(valor: string | null | undefined): string {
  if (!valor) return "—";
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleDateString("pt-BR");
}

function legenda(imagem: Imagem | null): string {
  if (!imagem) return "indisponível";
  return `${imagem.satellite || "Satélite não informado"} · ${formatarData(imagem.acquired_at)}`;
}

function FotoUnica({ titulo, imagem, aviso }: { titulo: string; imagem: Imagem; aviso: string }) {
  return (
    <figure className="foto-unica">
      <figcaption>
        <strong>{titulo}</strong>
        <span>{legenda(imagem)}</span>
      </figcaption>
      <img src={imagem.url} alt={`${titulo} do desmatamento`} />
      <p className="aviso">{aviso}</p>
    </figure>
  );
}

export function Comparador({ antes, depois }: { antes: Imagem | null; depois: Imagem | null }) {
  const [posicao, setPosicao] = useState(50);
  const [falhaAntes, setFalhaAntes] = useState(false);
  const [falhaDepois, setFalhaDepois] = useState(false);

  useEffect(() => {
    setPosicao(50);
    setFalhaAntes(false);
    setFalhaDepois(false);
  }, [antes?.url, depois?.url]);

  const fotoAntes = antes && !falhaAntes ? antes : null;
  const fotoDepois = depois && !falhaDepois ? depois : null;

  if (!fotoAntes && !fotoDepois) {
    return <p className="foto-vazia">Imagem indisponível para este alerta.</p>;
  }
  if (fotoAntes && !fotoDepois) {
    return (
      <FotoUnica
        titulo="Antes"
        imagem={fotoAntes}
        aviso="A imagem de depois não carregou para este alerta."
      />
    );
  }
  if (!fotoAntes && fotoDepois) {
    return (
      <FotoUnica
        titulo="Depois"
        imagem={fotoDepois}
        aviso="A imagem de antes não carregou para este alerta."
      />
    );
  }

  return (
    <div className="comparador">
      <img
        className="comparador-base"
        src={fotoAntes!.url}
        alt="Antes do desmatamento"
        onError={() => setFalhaAntes(true)}
      />
      <img
        className="comparador-topo"
        src={fotoDepois!.url}
        alt="Depois do desmatamento"
        style={{ clipPath: `inset(0 ${100 - posicao}% 0 0)` }}
        onError={() => setFalhaDepois(true)}
      />
      <span className="comparador-linha" style={{ left: `${posicao}%` }} />
      <span className="etiqueta antes">Antes</span>
      <span className="etiqueta depois">Depois</span>
      <input
        type="range"
        min={0}
        max={100}
        value={posicao}
        aria-label="Arraste para a direita para ver o depois e para a esquerda para ver o antes"
        onChange={(event) => setPosicao(Number(event.target.value))}
      />
      <p className="comparador-datas">
        <span>Antes · {legenda(fotoAntes)}</span>
        <span>Depois · {legenda(fotoDepois)}</span>
      </p>
    </div>
  );
}
