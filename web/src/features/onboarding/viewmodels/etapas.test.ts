import { describe, expect, it } from "vitest";
import { RASCUNHO_VAZIO } from "../models/perfil.model";
import { ETAPAS, etapaCompleta, podeIrPara } from "./etapas";

const idx = (e: (typeof ETAPAS)[number]) => ETAPAS.indexOf(e);

describe("etapas do quiz", () => {
  it("boas-vindas e município sempre acessíveis", () => {
    expect(podeIrPara(idx("boas-vindas"), RASCUNHO_VAZIO)).toBe(true);
    expect(podeIrPara(idx("municipio"), RASCUNHO_VAZIO)).toBe(true);
  });

  it("não pula para solo sem município", () => {
    expect(podeIrPara(idx("solo"), RASCUNHO_VAZIO)).toBe(false);
  });

  it("libera o fim só com tudo respondido", () => {
    const parcial = {
      ...RASCUNHO_VAZIO,
      municipio: { ponto_id: "crato_ce", nome: "Crato" },
      solo: "medio" as const,
    };
    expect(podeIrPara(idx("fim"), parcial)).toBe(false);
    expect(podeIrPara(idx("fim"), { ...parcial, clima: "semiarido" })).toBe(true);
  });

  it("etapas sem pergunta estão sempre completas", () => {
    expect(etapaCompleta("boas-vindas", RASCUNHO_VAZIO)).toBe(true);
    expect(etapaCompleta("fim", RASCUNHO_VAZIO)).toBe(true);
  });

  it("rejeita índices fora do intervalo", () => {
    expect(podeIrPara(-1, RASCUNHO_VAZIO)).toBe(false);
    expect(podeIrPara(ETAPAS.length, RASCUNHO_VAZIO)).toBe(false);
  });
});
