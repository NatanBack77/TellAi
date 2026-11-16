import { describe, expect, it } from "vitest";
import type { Municipio } from "../models/municipio.model";
import { filtrarMunicipios } from "./filtrarMunicipios";

const m = (ponto_id: string, nome: string): Municipio => ({
  ponto_id,
  nome,
  lat: 0,
  lon: 0,
  ibge: null,
});
const lista = [
  m("sobral_ce", "Sobral (CE)"),
  m("quixada_ce", "Quixadá (CE)"),
  m("crato_ce", "Crato (CE)"),
];

describe("filtrarMunicipios", () => {
  it("ordena alfabeticamente quando não há busca", () => {
    expect(filtrarMunicipios(lista, "").map((x) => x.ponto_id)).toEqual([
      "crato_ce",
      "quixada_ce",
      "sobral_ce",
    ]);
  });

  it("ignora acentos e caixa", () => {
    expect(filtrarMunicipios(lista, "QUIXADA").map((x) => x.ponto_id)).toEqual(["quixada_ce"]);
  });

  it("não altera a lista original", () => {
    const copia = [...lista];
    filtrarMunicipios(lista, "");
    expect(lista).toEqual(copia);
  });
});
