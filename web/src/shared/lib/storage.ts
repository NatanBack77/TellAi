import type { z } from "zod";

/**
 * Leitura/escrita segura no localStorage: nunca lança (modo privado, cota cheia,
 * storage bloqueado) e valida o conteúdo com zod — dado inválido conta como ausente.
 */
export function lerStorage<S extends z.ZodType>(chave: string, schema: S): z.infer<S> | null {
  try {
    const bruto = localStorage.getItem(chave);
    if (!bruto) return null;
    const r = schema.safeParse(JSON.parse(bruto));
    return r.success ? r.data : null;
  } catch {
    return null;
  }
}

export function gravarStorage(chave: string, valor: unknown): boolean {
  try {
    localStorage.setItem(chave, JSON.stringify(valor));
    return true;
  } catch {
    return false;
  }
}

export function apagarStorage(chave: string) {
  try {
    localStorage.removeItem(chave);
  } catch {
    /* ignora */
  }
}
