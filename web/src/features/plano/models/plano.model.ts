import { z } from "zod";
import type { TopicoId } from "@/features/painel/models/topicos.model";

/**
 * Model: contrato de POST /plano-plantio (ver docs/34_PLANO_DE_PLANTIO.md).
 * O servidor já aplica as regras do produto (sem caminho de arquivo, sem produto/defensivo, lacuna sem valor);
 * aqui só validamos o formato para o erro aparecer na borda e não no meio da tela.
 */
export const STATUS_ITEM = ["verificado", "calculado", "lacuna", "nao_se_aplica"] as const;

export const fonteSchema = z.object({
  nome: z.string(),
  pagina: z.number().nullable(),
  url: z.string().nullable(),
});

export const itemSchema = z.object({
  atributo: z.string(),
  rotulo: z.string(),
  /** null = lacuna ou "não se aplica". Nunca é preenchido pelo front. */
  valor: z.string().nullable(),
  unidade: z.string(),
  status: z.enum(STATUS_ITEM),
  fonte: fonteSchema.nullable(),
  trecho: z.string().nullable(),
  /** De onde vem (região da fonte, limites). Mostrar junto do valor. */
  contexto: z.string(),
  requer_tecnico: z.boolean(),
  /** É o que a fonte diz, NÃO é recomendação para o terreno do agricultor (adubação). */
  referencia_da_fonte: z.boolean(),
  /** Valor de parcela de experimento, não recomendação de plantio. */
  experimento: z.boolean(),
  /** Faz parte da resposta objetiva da etapa (até 3): mostrar primeiro; o resto vai em "detalhes". */
  destaque: z.boolean(),
});

export const etapaSchema = z.object({
  numero: z.number().int(),
  slug: z.string(),
  titulo: z.string(),
  origem: z.enum(["dado_curado", "motor"]),
  itens: z.array(itemSchema),
  /** O que NÃO temos nesta etapa. Mostrar sempre. */
  lacunas: z.array(z.string()),
  nao_se_aplica: z.boolean(),
  aviso_tecnico: z.boolean(),
});

export const planoSchema = z.object({
  versao: z.string(),
  ponto_id: z.string(),
  cultura: z.string(),
  cultura_nome: z.string(),
  /** true = a cultura é um exemplo escolhido pelo servidor (a etapa 2 cita qual é). */
  cultura_exemplo: z.boolean(),
  etapas: z.array(etapaSchema),
  cobertura_itens: z.record(z.string(), z.number()),
  limites: z.array(z.string()),
  aviso: z.string(),
});

export const culturasPlanoSchema = z.array(
  z.object({
    cultura: z.string(),
    nome: z.string(),
    itens_por_etapa: z.record(z.string(), z.number()),
  }),
);

/** Textura do solo que a pessoa informou, no formato da API ("qualquer" = não sei). */
export type SoloPlano = "qualquer" | "arenoso" | "medio" | "argiloso";

export type Fonte =z.infer<typeof fonteSchema>;
export type ItemPlano = z.infer<typeof itemSchema>;
export type EtapaPlano = z.infer<typeof etapaSchema>;
export type Plano = z.infer<typeof planoSchema>;
export type CulturaPlano = z.infer<typeof culturasPlanoSchema>[number];

/** Tópico da tela → número da etapa no back-end (mesma ordem e mesmos nomes do docs/34). */
export const NUMERO_DA_ETAPA: Record<TopicoId, number> = {
  introducao: 1,
  recomendacao: 2,
  clima: 3,
  "preparo-solo": 4,
  semeadura: 5,
  irrigacao: 6,
  adubacao: 7,
  manutencao: 8,
  colheita: 9,
  "pos-colheita": 10,
};
