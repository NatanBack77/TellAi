/** Remove acentos e caixa para comparar textos digitados com nomes de lugares. */
export function normalizeSearch(value: string) {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("pt-BR").trim();
}
