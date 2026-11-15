import { queryOptions } from "@tanstack/react-query";
import type { SoloPlano } from "../models/plano.model";
import { planoService } from "../services/plano.service";

/** O plano só muda quando o dado curado é regerado: guardamos por bastante tempo. Uma consulta por local. */
export const planoQueryOptions = (pontoId: string, solo: SoloPlano) =>
  queryOptions({
    queryKey: ["plano-plantio", pontoId, solo],
    queryFn: ({ signal }) => planoService.obter(pontoId, solo, signal),
    staleTime: 30 * 60_000,
    retry: 1,
  });
