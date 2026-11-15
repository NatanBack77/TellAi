import { normalizeSearch } from "@/shared/lib/text";
import { nomeCurto, type Municipio } from "../models/municipio.model";

/** Regra de apresentação pura (testável sem React): filtra por nome e ordena alfabeticamente. */
export function filtrarMunicipios(lista: readonly Municipio[], busca: string): Municipio[] {
  const termo = normalizeSearch(busca);
  return lista
    .filter((m) => !termo || normalizeSearch(m.nome).includes(termo))
    .sort((a, b) => nomeCurto(a).localeCompare(nomeCurto(b), "pt-BR"));
}
