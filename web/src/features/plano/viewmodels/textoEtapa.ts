import type { EtapaPlano, ItemPlano } from "../models/plano.model";

/**
 * Geração do TEXTO de cada etapa a partir do que o back-end devolveu. Função pura (sem React): é onde as regras do produto viram frase.
 * Nunca inventa valor: só junta o que veio; lacuna vira "ainda não temos", nunca número.
 *
 * Resposta objetiva = `destaques` (até 3, escolhidos pelo servidor); o resto vai em `detalhes`.
 */
export type TipoSelo = "tecnico" | "referencia" | "experimento";

export interface Selo {
  tipo: TipoSelo;
  rotulo: string;
  /** Frase completa (dica ao passar o mouse / leitor de tela). */
  dica: string;
}

export interface LinhaTexto {
  rotulo: string;
  valor: string;
  /** "Embrapa …, p. 12" — ou, para itens do motor, a origem do cálculo. */
  fonte: string | null;
  /** De onde vem (região da fonte, limites). Texto pequeno junto do valor. */
  origem: string | null;
  /** Avisos curtos que acompanham o valor. */
  selos: Selo[];
  destaque: boolean;
}

export interface TextoEtapa {
  /** Todas as linhas, na ordem do servidor. */
  linhas: LinhaTexto[];
  /** A resposta objetiva: até 3 linhas. */
  destaques: LinhaTexto[];
  /** O resto, para quem quer ver mais. */
  detalhes: LinhaTexto[];
  /** O que não temos nesta etapa (sempre mostrar). */
  faltas: string[];
  naoSeAplica: boolean;
  /** true = nenhum dado com fonte nesta etapa (só lacunas). */
  semDados: boolean;
}

export const NOTA_TECNICO = "Converse com o técnico antes de aplicar.";
export const NOTA_REFERENCIA = "É o que a fonte diz; não é recomendação para o seu terreno.";
export const NOTA_EXPERIMENTO = "Valor de um experimento; não é recomendação de plantio.";

// Número "solto" (ex.: "6 a 10", "menos de 10", "24 (2 anos)"): só nesses casos a unidade vai colada. Texto livre já traz a sua unidade.
const NUMERICO = /^((?:menos de |mais de )?[\d.,]+(?: (?:a|e) [\d.,]+)?)(\s*\(.*\))?$/;

export function formatarValor(valor: string, unidade: string): string {
  const u = unidade.trim();
  if (!u) return valor;
  const m = NUMERICO.exec(valor.trim());
  return m ? `${m[1]} ${u}${m[2] ?? ""}` : valor;
}

export function textoFonte(item: ItemPlano): string | null {
  if (!item.fonte) return null;
  const { nome, pagina } = item.fonte;
  return pagina ? `${nome}, p. ${pagina}` : nome;
}

function selosDoItem(item: ItemPlano): Selo[] {
  const selos: Selo[] = [];
  if (item.referencia_da_fonte) selos.push({ tipo: "referencia", rotulo: "Referência da fonte", dica: NOTA_REFERENCIA });
  if (item.experimento) selos.push({ tipo: "experimento", rotulo: "Experimento", dica: NOTA_EXPERIMENTO });
  if (item.requer_tecnico) selos.push({ tipo: "tecnico", rotulo: "Falar com o técnico", dica: NOTA_TECNICO });
  return selos;
}

export function textoDaEtapa(etapa: EtapaPlano): TextoEtapa {
  const linhas: LinhaTexto[] = [];
  const faltas = [...etapa.lacunas];
  for (const item of etapa.itens) {
    if (item.valor === null || item.valor.trim() === "") {
      // Defesa: o servidor não manda item sem valor, mas se mandar é lacuna, não linha vazia.
      faltas.push(`${item.rotulo}: sem dado.`);
      continue;
    }
    linhas.push({
      rotulo: item.rotulo,
      valor: formatarValor(item.valor, item.unidade),
      fonte: textoFonte(item),
      origem: item.contexto.trim() || null,
      selos: selosDoItem(item),
      destaque: item.destaque,
    });
  }
  const destaques = linhas.filter((l) => l.destaque);
  // Defesa: se o servidor não marcou nenhum destaque, as 3 primeiras linhas viram a resposta objetiva.
  const resposta = destaques.length > 0 ? destaques : linhas.slice(0, 3);
  return {
    linhas,
    destaques: resposta,
    detalhes: linhas.filter((l) => !resposta.includes(l)),
    faltas,
    naoSeAplica: etapa.nao_se_aplica,
    semDados: linhas.length === 0,
  };
}
