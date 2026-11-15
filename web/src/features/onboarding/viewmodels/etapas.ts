import type { RascunhoPerfil } from "../models/perfil.model";

/** Ordem das telas do quiz. "boas-vindas" fica fora do stepper. */
export const ETAPAS = ["boas-vindas", "municipio", "solo", "clima", "fim"] as const;
export type Etapa = (typeof ETAPAS)[number];

/** Rótulos do stepper (da etapa 1 em diante). */
export const PASSOS_STEPPER = ["Município", "Solo", "Clima", "Concluído"] as const;

/** A etapa já tem resposta suficiente para avançar? */
export function etapaCompleta(etapa: Etapa, r: RascunhoPerfil): boolean {
  switch (etapa) {
    case "municipio":
      return r.municipio !== null;
    case "solo":
      return r.solo !== null;
    case "clima":
      return r.clima !== null;
    default:
      return true;
  }
}

/** Pode chegar na etapa `alvo` se todas as anteriores estão respondidas. */
export function podeIrPara(alvo: number, r: RascunhoPerfil): boolean {
  if (alvo < 0 || alvo >= ETAPAS.length) return false;
  return ETAPAS.slice(0, alvo).every((e) => etapaCompleta(e, r));
}
