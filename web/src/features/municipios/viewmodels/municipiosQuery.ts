import { queryOptions } from "@tanstack/react-query";
import { municipiosService } from "../services/municipios.service";

export const municipiosQueryOptions = () =>
  queryOptions({
    queryKey: ["municipios"],
    queryFn: ({ signal }) => municipiosService.listar(signal),
    staleTime: 10 * 60_000, // a lista de pontos quase não muda
  });
