import { z } from "zod";

/**
 * Model: respostas do quiz inicial, guardadas no localStorage.
 *
 * Opções vindas das bases do projeto:
 * - Solo: textura usada pelo ZARC (Cod_Solo 1/2/3 = arenoso/médio/argiloso, src/culturas/zarc.py)
 *   e pela API (`textura`: "não sei" | "arenoso" | "médio" | "argiloso").
 * - Clima: `Nome_Clima` do ZARC do Ceará (data/processed/zarc_ce.parquet): Semiárido, Tropical, Quente.
 */
export const SOLOS = ["arenoso", "medio", "argiloso", "nao_sei"] as const;
export const CLIMAS = ["semiarido", "tropical", "quente", "nao_sei"] as const;

export type Solo = (typeof SOLOS)[number];
export type Clima = (typeof CLIMAS)[number];

export const perfilSchema = z.object({
  versao: z.literal(2),
  municipio: z.object({ ponto_id: z.string(), nome: z.string() }),
  solo: z.enum(SOLOS),
  clima: z.enum(CLIMAS),
  concluidoEm: z.string(),
});

export type Perfil = z.infer<typeof perfilSchema>;

/** Rascunho durante o quiz: tudo opcional até o fim. */
export interface RascunhoPerfil {
  municipio: Perfil["municipio"] | null;
  solo: Solo | null;
  clima: Clima | null;
}

export const RASCUNHO_VAZIO: RascunhoPerfil = { municipio: null, solo: null, clima: null };

export const ROTULO_SOLO: Record<Solo, string> = {
  arenoso: "Arenoso",
  medio: "Médio",
  argiloso: "Argiloso",
  nao_sei: "Não sei",
};

export const DESCRICAO_SOLO: Record<Solo, string> = {
  arenoso: "Solto e claro, não forma bolo na mão e seca rápido.",
  medio: "Meio-termo: forma um bolo que se desfaz fácil.",
  argiloso: "Gruda e forma bolo firme quando molhado; racha na seca.",
  nao_sei: "Sem problema: usamos a estimativa do mapa de solos para o seu local.",
};

export const ROTULO_CLIMA: Record<Clima, string> = {
  semiarido: "Semiárido",
  tropical: "Tropical",
  quente: "Quente",
  nao_sei: "Não sei",
};

export const DESCRICAO_CLIMA: Record<Clima, string> = {
  semiarido: "Pouca chuva, concentrada em poucos meses, e seca longa.",
  tropical: "Estação de chuvas bem marcada e o resto do ano mais seco.",
  quente: "Calor o ano todo, com chuva mais irregular.",
  nao_sei: "Sem problema: usamos a classificação do zoneamento (ZARC) do seu município.",
};

/** Valor de `textura` que a API espera. */
export const TEXTURA_API: Record<Solo, "arenoso" | "médio" | "argiloso" | "não sei"> = {
  arenoso: "arenoso",
  medio: "médio",
  argiloso: "argiloso",
  nao_sei: "não sei",
};
