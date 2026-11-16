import type { Perfil, Solo } from "@/features/onboarding/models/perfil.model";
import { ROTULO_CLIMA } from "@/features/onboarding/models/perfil.model";
import type { ContextoMaira } from "../models/conversa.model";

const TEXTURA_API: Record<Solo, ContextoMaira["textura"]> = {
  arenoso: "arenoso",
  medio: "médio",
  argiloso: "argiloso",
  nao_sei: "não sei",
};

/** O que a pessoa respondeu no quiz, no formato da API. Nada é inventado: "não sei" vai como "não sei". */
export function montarContexto(perfil: Perfil): ContextoMaira {
  return {
    pontoId: perfil.municipio.ponto_id,
    municipio: perfil.municipio.nome,
    textura: TEXTURA_API[perfil.solo],
    clima: ROTULO_CLIMA[perfil.clima],
  };
}

/** Frases para a tela: o que a Maíra já sabe. */
export function resumoDoContexto(ctx: ContextoMaira): string[] {
  return [ctx.municipio, ctx.textura === "não sei" ? "solo: não sei" : `solo ${ctx.textura}`, `clima ${ctx.clima.toLowerCase()}`];
}
