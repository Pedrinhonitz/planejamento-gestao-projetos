import { useEffect } from "react";
import { CircleMarker, GeoJSON, MapContainer, Rectangle, TileLayer, useMap } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import type { Linha } from "./types";

type Ponto = [number, number];

const CORES: Record<string, string> = {
  alta: "#9b2335",
  media: "#a15c07",
  baixa: "#1f6b45",
};

function corPrioridade(prioridade: string | undefined): string {
  return CORES[prioridade ?? ""] ?? "#3d4a44";
}

function caminhar(coords: unknown, saida: Ponto[]) {
  if (!Array.isArray(coords) || coords.length === 0) return;
  if (typeof coords[0] === "number" && typeof coords[1] === "number") {
    saida.push([coords[1] as number, coords[0] as number]);
    return;
  }
  for (const item of coords) caminhar(item, saida);
}

export function pontosDaLinha(linha: Linha): Ponto[] {
  const pontos: Ponto[] = [];
  const geometry = linha.resultado.geometry;
  if (geometry) caminhar(geometry.coordinates, pontos);
  const bbox = linha.alerta?.bbox;
  if (bbox) {
    for (const par of bbox) pontos.push([par[1], par[0]]);
  }
  const ponto = linha.alerta?.ponto;
  if (ponto) pontos.push([ponto[1], ponto[0]]);
  return pontos;
}

function limites(pontos: Ponto[]): LatLngBoundsExpression | null {
  if (pontos.length === 0) return null;
  let sul = pontos[0][0];
  let norte = pontos[0][0];
  let oeste = pontos[0][1];
  let leste = pontos[0][1];
  for (const [lat, lng] of pontos) {
    sul = Math.min(sul, lat);
    norte = Math.max(norte, lat);
    oeste = Math.min(oeste, lng);
    leste = Math.max(leste, lng);
  }
  if (sul === norte && oeste === leste) {
    return [
      [sul - 0.02, oeste - 0.02],
      [norte + 0.02, leste + 0.02],
    ];
  }
  return [
    [sul, oeste],
    [norte, leste],
  ];
}

function imoveisUnicos(linhas: Linha[]): Linha[] {
  const vistos = new Set<string>();
  const unicos: Linha[] = [];
  for (const linha of linhas) {
    if (vistos.has(linha.resultado.car_code)) continue;
    vistos.add(linha.resultado.car_code);
    unicos.push(linha);
  }
  return unicos;
}

function Enquadrar({ bounds, chave }: { bounds: LatLngBoundsExpression | null; chave: string }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [28, 28], maxZoom: 16 });
  }, [chave, map]);
  return null;
}

function AjustarTamanho() {
  const map = useMap();
  useEffect(() => {
    const ajustar = () => map.invalidateSize();
    document.addEventListener("fullscreenchange", ajustar);
    return () => document.removeEventListener("fullscreenchange", ajustar);
  }, [map]);
  return null;
}

function Camada({
  linha,
  ativo,
  onSelect,
}: {
  linha: Linha;
  ativo: boolean;
  onSelect: (key: string) => void;
}) {
  const bbox = linha.alerta?.bbox;
  const ponto = linha.alerta?.ponto;
  return (
    <>
      {bbox && (
        <Rectangle
          bounds={[
            [bbox[0][1], bbox[0][0]],
            [bbox[1][1], bbox[1][0]],
          ]}
          pathOptions={{
            color: "#fffdf8",
            weight: ativo ? 3 : 2,
            fillColor: corPrioridade(linha.alerta?.prioridade),
            fillOpacity: ativo ? 0.28 : 0.12,
          }}
          eventHandlers={{ click: () => onSelect(linha.key) }}
        />
      )}
      {ponto && (
        <CircleMarker
          center={[ponto[1], ponto[0]]}
          radius={ativo ? 8 : 5}
          pathOptions={{
            color: "#fff",
            weight: 2,
            fillColor: corPrioridade(linha.alerta?.prioridade),
            fillOpacity: 1,
          }}
          eventHandlers={{ click: () => onSelect(linha.key) }}
        />
      )}
    </>
  );
}

type Props = {
  linhas: Linha[];
  selecionada: string | null;
  onSelect: (key: string) => void;
};

export function Mapa({ linhas, selecionada, onSelect }: Props) {
  const foco = linhas.find((linha) => linha.key === selecionada) ?? null;
  const pontos = foco ? pontosDaLinha(foco) : linhas.flatMap(pontosDaLinha);
  const bounds = limites(pontos);

  const chaveMapa = `${selecionada ?? "tudo"}:${pontos.length}`;

  return (
    <MapContainer center={[-10.8, -68.7]} zoom={6} maxZoom={18} className="mapa" scrollWheelZoom>
      <TileLayer
        attribution="Tiles &copy; Esri"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        maxNativeZoom={18}
        maxZoom={18}
      />
      <TileLayer
        attribution="Labels &copy; Esri"
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
        maxNativeZoom={18}
        maxZoom={18}
      />
      <Enquadrar bounds={bounds} chave={chaveMapa} />
      <AjustarTamanho />
      {imoveisUnicos(linhas).map((linha) =>
        linha.resultado.geometry ? (
          <GeoJSON
            key={`${linha.resultado.car_code}-${linha.resultado.car_code === foco?.resultado.car_code}`}
            data={
              {
                type: "Feature",
                geometry: linha.resultado.geometry as GeoJSON.Geometry,
                properties: {},
              } as GeoJSON.Feature
            }
            style={{
              color: "#fffdf8",
              weight: linha.resultado.car_code === foco?.resultado.car_code ? 3 : 2,
              fillColor: linha.resultado.car_code === foco?.resultado.car_code ? "#f6e27a" : "#fffdf8",
              fillOpacity: 0.08,
            }}
            eventHandlers={{ click: () => onSelect(linha.key) }}
          />
        ) : null,
      )}
      {linhas.map((linha) => (
        <Camada
          key={linha.key}
          linha={linha}
          ativo={linha.key === selecionada}
          onSelect={onSelect}
        />
      ))}
    </MapContainer>
  );
}
