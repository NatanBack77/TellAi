import { http } from "@/shared/api/httpClient";
import { respostaSchema, type ContextoMaira, type Estado } from "../models/conversa.model";

/** Service: único ponto que conhece o /conversa. O contexto vai em campos próprios (ponto_id, perfil), não dentro da mensagem. */
export const conversaService = {
  enviar: (mensagem: string, estado: Estado | null, ctx: ContextoMaira, signal?: AbortSignal) =>
    http.post(
      "/conversa",
      respostaSchema,
      { mensagem, estado, ponto_id: ctx.pontoId, perfil: { textura: ctx.textura } },
      { signal, timeoutMs: 100_000 },
    ),
};
