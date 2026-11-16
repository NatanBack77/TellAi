import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { municipiosQueryOptions } from "./municipiosQuery";
import { filtrarMunicipios } from "./filtrarMunicipios";

const route = getRouteApi("/_app/municipios");

/**
 * ViewModel: junta dados (Model/Service), estado da URL e estado de tela,
 * e entrega para a View só o que ela precisa desenhar e os comandos que ela pode disparar.
 */
export function useMunicipiosViewModel() {
  const { q: busca = "" } = route.useSearch();
  const navigate = route.useNavigate();
  const query = useQuery(municipiosQueryOptions());
  const [selecionadoId, setSelecionadoId] = useState<string | null>(null);

  const todos = useMemo(() => query.data ?? [], [query.data]);
  const filtrados = useMemo(() => filtrarMunicipios(todos, busca), [todos, busca]);
  const selecionado = todos.find((m) => m.ponto_id === selecionadoId) ?? null;

  return {
    // estado
    busca,
    todos,
    filtrados,
    selecionado,
    total: todos.length,
    carregando: query.isPending,
    erro: query.isError,
    // comandos
    buscar: (q: string) => navigate({ search: { q: q || undefined }, replace: true }),
    selecionar: (id: string | null) => setSelecionadoId(id),
    tentarDeNovo: () => query.refetch(),
  };
}

export type MunicipiosViewModel = ReturnType<typeof useMunicipiosViewModel>;
