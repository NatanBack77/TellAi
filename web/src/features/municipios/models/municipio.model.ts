import { z } from "zod";

/** Model: contrato de GET /municipios (ver docs/12_API.md). `ibge: null` é lacuna, não erro. */
export const municipioSchema = z.object({
  ponto_id: z.string(),
  nome: z.string(),
  lat: z.number(),
  lon: z.number(),
  ibge: z.number().nullable(),
});
export const municipiosSchema = z.array(municipioSchema);

export type Municipio = z.infer<typeof municipioSchema>;

/** "quixada_ce" → "CE" */
export function ufDoMunicipio(m: Municipio) {
  return m.ponto_id.split("_").at(-1)?.toUpperCase() ?? "";
}

/** "Quixada (CE)" → "Quixada" */
export function nomeCurto(m: Pick<Municipio, "nome">) {
  return m.nome.replace(/\s*\([A-Z]{2}\)$/, "");
}
