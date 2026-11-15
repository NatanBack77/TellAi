import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { SoloPlano } from "../models/plano.model";
import { planoQueryOptions } from "./planoQuery";
import { textoDaEtapa } from "./textoEtapa";

/**
 * ViewModel: o texto de UMA etapa do plano para o local do agricultor.
 * Busca o plano inteiro uma vez (as 10 etapas vêm juntas e ficam em cache) e entrega só a etapa pedida.
 * A cultura é um EXEMPLO escolhido pelo servidor; a etapa 2 diz qual é.
 */
export function usePlanoViewModel(pontoId: string | null, solo: SoloPlano, numeroEtapa: number) {
  const planoQuery = useQuery({ ...planoQueryOptions(pontoId ?? "", solo), enabled: Boolean(pontoId) });

  const etapa = planoQuery.data?.etapas.find((e) => e.numero === numeroEtapa);
  const texto = useMemo(() => (etapa ? textoDaEtapa(etapa) : null), [etapa]);

  return {
    // estado
    semLocal: !pontoId,
    culturaNome: planoQuery.data?.cultura_nome ?? null,
    culturaExemplo: planoQuery.data?.cultura_exemplo ?? false,
    carregando: Boolean(pontoId) && planoQuery.isPending,
    erro: Boolean(pontoId) && planoQuery.isError,
    texto,
    aviso: planoQuery.data?.aviso ?? null,
    limites: planoQuery.data?.limites ?? [],
    // comandos
    tentarDeNovo: () => void planoQuery.refetch(),
  };
}

export type PlanoViewModel = ReturnType<typeof usePlanoViewModel>;
