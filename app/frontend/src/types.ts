export type Imagem = {
  url: string;
  acquired_at: string | null;
  satellite: string | null;
};

export type Alerta = {
  alert_code: string | null;
  area_alerta_ha: number | null;
  detected_at: string | null;
  published_at: string | null;
  fonte: string;
  status_alerta: string;
  prioridade: string;
  proba_alta: number | null;
  proba_media: number | null;
  proba_baixa: number | null;
  bbox: [number, number][] | null;
  ponto: [number, number] | null;
  imagem_antes: Imagem | null;
  imagem_depois: Imagem | null;
};

export type Geometria = {
  type: string;
  coordinates: unknown;
};

export type Resultado = {
  car_code: string;
  municipio: string | null;
  uf: string | null;
  status_imovel: string | null;
  condicao: string | null;
  tipo_imovel: string | null;
  area_imovel_ha: number | null;
  modulos_fiscais: number | null;
  geometry: Geometria | null;
  aviso: string | null;
  erro: string | null;
  alertas: Alerta[];
};

export type Linha = {
  key: string;
  resultado: Resultado;
  alerta: Alerta | null;
};

export const CAR_RE = /^[A-Z]{2}-\d{7}-[A-F0-9]{32}$/;
