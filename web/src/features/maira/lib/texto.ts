/** Helpers de texto do chat, portados do chat antigo (frontend/src/App.tsx). Funções puras. */

const sem = (t: string) =>
  t
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[.,!?;:]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/** "Entendi: ..." só aparece quando acrescenta algo à pergunta (se só repete o que a pessoa disse, some). */
export function entendidoUtil(valor: string | null | undefined, pergunta: string): string | null {
  if (!valor) return null;
  const texto = valor.replace(/^\s*entendi\s*:\s*/i, "").trim();
  if (!texto) return null;
  const e = sem(texto);
  const p = sem(pergunta);
  if (!e || e === p || p.includes(e) || e.includes(p)) return null;
  return texto;
}

/** **trecho** vira negrito; o resto é texto puro (nunca HTML vindo do servidor). */
export function dividirNegrito(texto: string): { texto: string; negrito: boolean }[] {
  return texto
    .split(/(\*\*[^*]+\*\*)/g)
    .filter((p) => p !== "")
    .map((p) => (/^\*\*[^*]+\*\*$/.test(p) ? { texto: p.slice(2, -2), negrito: true } : { texto: p, negrito: false }));
}
