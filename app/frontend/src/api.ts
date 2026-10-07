import type { Resultado } from "./types";

export async function consultar(carCodes: string[]): Promise<Resultado[]> {
  const response = await fetch("/api/consultar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ car_codes: carCodes }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(mensagemErro(data));
  }
  return (data.resultados ?? []) as Resultado[];
}

function mensagemErro(data: { detail?: unknown }): string {
  if (typeof data.detail === "string" && data.detail.trim()) {
    return data.detail;
  }
  return "Não foi possível consultar os códigos CAR.";
}
