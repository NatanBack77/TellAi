import { http } from "@/shared/api/httpClient";
import { planoSchema, type SoloPlano } from "../models/plano.model";

/** Service: único ponto que conhece a URL do plano de plantio. Sem cultura no pedido, o servidor usa uma cultura de exemplo do local. A 1ª chamada de cada local leva alguns segundos (motor). */
export const planoService = {
  obter: (pontoId: string, solo: SoloPlano, signal?: AbortSignal) =>
    http.post("/plano-plantio", planoSchema, { ponto_id: pontoId, solo }, { signal, timeoutMs: 90_000 }),
};
