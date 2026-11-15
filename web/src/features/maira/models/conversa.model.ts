import { z } from "zod";

/**
 * Model: contrato de POST /conversa (ver docs/32_FRONTEND_HANDOFF.md). O servidor NÃO guarda a conversa:
 * o front devolve o `estado` exatamente como recebeu, sem editar. Texto do modelo só entra como texto (nunca HTML).
 */
export const chipSchema = z.object({ rotulo: z.string(), texto: z.string() });

export const fonteSchema = z.object({ id: z.string(), rotulo: z.string(), texto_simples: z.string(), lacuna: z.boolean() });

export const respostaSchema = z.object({
  resposta: z.string(),
  estado: z.record(z.string(), z.unknown()),
  acao: z.enum(["responder", "perguntar", "confirmar", "recusar"]),
  chips: z.array(chipSchema),
  entendido: z.string().nullable(),
  fontes: z.array(fonteSchema),
  assistente: z.string(),
});

export type RespostaMaira = z.infer<typeof respostaSchema>;
export type Chip = z.infer<typeof chipSchema>;
export type FonteMaira = z.infer<typeof fonteSchema>;
export type Estado = RespostaMaira["estado"];

export interface Mensagem {
  papel: "usuario" | "maira";
  texto: string;
  /** Só nas respostas: "Entendi: …" (quando acrescenta algo) e "De onde veio esta resposta". */
  entendido?: string | null;
  fontes?: FonteMaira[];
}

/** Tudo o que a pessoa informou no app e que a Maíra recebe junto de cada mensagem. A cultura do plano NÃO vai: ela não planta isso hoje. */
export interface ContextoMaira {
  pontoId: string;
  municipio: string;
  /** Textura do solo no formato da API: "arenoso" | "médio" | "argiloso" | "não sei". */
  textura: "arenoso" | "médio" | "argiloso" | "não sei";
  clima: string;
}
