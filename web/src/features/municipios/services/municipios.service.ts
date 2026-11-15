import { http } from "@/shared/api/httpClient";
import { municipiosSchema, type Municipio } from "../models/municipio.model";
import fallback from "../models/municipios-fallback.json";

/** Cópia de data/processed/pontos.csv embutida no build: usada quando a API está fora do ar. */
const FALLBACK: Municipio[] = municipiosSchema.parse(fallback);

/** Service: único ponto que conhece a URL e o formato do back-end. */
export const municipiosService = {
  listar: async (signal?: AbortSignal): Promise<Municipio[]> => {
    try {
      return await http.get("/municipios", municipiosSchema, { signal, timeoutMs: 8_000 });
    } catch (erro) {
      if (signal?.aborted) throw erro;
      console.warn("API de municípios indisponível; usando a lista local.", erro);
      return FALLBACK;
    }
  },
};
