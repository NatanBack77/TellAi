import { describe, expect, it } from "vitest";
import { IDS_TOPICOS } from "@/features/painel/models/topicos.model";
import culturas from "../models/fixtures/culturas.json";
import milho from "../models/fixtures/plano-milho-quixada.json";
import mucuna from "../models/fixtures/plano-mucuna-quixada.json";
import exemplo from "../models/fixtures/plano-exemplo-quixada.json";
import { culturasPlanoSchema, NUMERO_DA_ETAPA, planoSchema, type EtapaPlano, type ItemPlano } from "../models/plano.model";
import { formatarValor, NOTA_REFERENCIA, NOTA_TECNICO, textoDaEtapa } from "./textoEtapa";

// As fixtures são respostas REAIS do back-end (src/api/rota_plano.py): se o contrato mudar, estes testes quebram na borda.
const planoMilho = planoSchema.parse(milho);
const planoMucuna = planoSchema.parse(mucuna);

const item = (p: Partial<ItemPlano> = {}): ItemPlano => ({
  atributo: "espacamento",
  rotulo: "Espaçamento",
  valor: "80 cm",
  unidade: "",
  status: "verificado",
  fonte: { nome: "Embrapa X", pagina: 12, url: null },
  trecho: null,
  contexto: "",
  requer_tecnico: false,
  referencia_da_fonte: false,
  experimento: false,
  destaque: false,
  ...p,
});
const etapa = (itens: ItemPlano[], extra: Partial<EtapaPlano> = {}): EtapaPlano => ({
  numero: 5, slug: "semeadura", titulo: "Semeadura e Plantio", origem: "dado_curado", itens, lacunas: [], nao_se_aplica: false, aviso_tecnico: true, ...extra,
});

describe("contrato com o back-end", () => {
  it("aceita a resposta real do plano e da lista de culturas", () => {
    expect(planoMilho.etapas).toHaveLength(10);
    expect(planoMucuna.etapas).toHaveLength(10);
    expect(culturasPlanoSchema.parse(culturas)).toHaveLength(16);
  });

  it("sem cultura no pedido o servidor escolhe a planta mais indicada, e a etapa 2 lista as opções com a época de plantio do solo", () => {
    const p = planoSchema.parse(exemplo);
    expect(p.cultura_exemplo).toBe(true);
    const e2 = textoDaEtapa(p.etapas[1]!);
    expect(e2.linhas[0]!.rotulo).toBe(p.cultura_nome);
    expect(e2.linhas[0]!.valor).toMatch(/Época de plantio \(solo médio\)/);
    expect(JSON.stringify(e2)).not.toMatch(/exemplo|empate|decêndio|quinzena/i);
    expect(planoMilho.cultura_exemplo).toBe(false);
  });

  it("os 10 tópicos da tela correspondem, na ordem, às 10 etapas do back-end", () => {
    expect(IDS_TOPICOS.map((id) => NUMERO_DA_ETAPA[id])).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(planoMilho.etapas.map((e) => e.numero)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  });
});

describe("textoDaEtapa", () => {
  it("monta rótulo, valor e fonte com página", () => {
    const t = textoDaEtapa(etapa([item()]));
    expect(t.linhas[0]).toMatchObject({ rotulo: "Espaçamento", valor: "80 cm", fonte: "Embrapa X, p. 12", origem: null, selos: [] });
    expect(t.semDados).toBe(false);
  });

  it("fonte sem página mostra só o nome", () => {
    const t = textoDaEtapa(etapa([item({ fonte: { nome: "Sulco: motor", pagina: null, url: null } })]));
    expect(t.linhas[0]?.fonte).toBe("Sulco: motor");
  });

  it("avisos viram selos curtos (com a frase inteira na dica) e a origem fica à parte", () => {
    const t = textoDaEtapa(etapa([item({ contexto: "Meio-Norte (PI/MA)", referencia_da_fonte: true, requer_tecnico: true })]));
    const l = t.linhas[0]!;
    expect(l.origem).toBe("Meio-Norte (PI/MA)");
    expect(l.selos.map((s) => s.tipo)).toEqual(["referencia", "tecnico"]);
    expect(l.selos.map((s) => s.dica)).toEqual([NOTA_REFERENCIA, NOTA_TECNICO]);
    expect(l.selos.every((s) => s.rotulo.length <= 22)).toBe(true);
  });

  it("item sem valor vira lacuna, nunca linha vazia", () => {
    const t = textoDaEtapa(etapa([item({ valor: null })]));
    expect(t.linhas).toHaveLength(0);
    expect(t.faltas).toEqual(["Espaçamento: sem dado."]);
    expect(t.semDados).toBe(true);
  });

  it("mantém as lacunas do servidor e o 'não se aplica'", () => {
    const t = textoDaEtapa(etapa([], { lacunas: ["Preço e venda: sem série de preço."], nao_se_aplica: true }));
    expect(t.faltas).toEqual(["Preço e venda: sem série de preço."]);
    expect(t.naoSeAplica).toBe(true);
  });
});

describe("resposta objetiva: destaques x detalhes", () => {
  it("destaques vêm do servidor; o resto vai para detalhes", () => {
    const t = textoDaEtapa(etapa([item({ rotulo: "A", destaque: true }), item({ rotulo: "B" }), item({ rotulo: "C", destaque: true })]));
    expect(t.destaques.map((l) => l.rotulo)).toEqual(["A", "C"]);
    expect(t.detalhes.map((l) => l.rotulo)).toEqual(["B"]);
  });

  it("sem nenhum destaque, as 3 primeiras linhas viram a resposta objetiva", () => {
    const t = textoDaEtapa(etapa(["A", "B", "C", "D"].map((r) => item({ rotulo: r }))));
    expect(t.destaques.map((l) => l.rotulo)).toEqual(["A", "B", "C"]);
    expect(t.detalhes.map((l) => l.rotulo)).toEqual(["D"]);
  });

  it("nada some: destaques + detalhes = todas as linhas", () => {
    for (const p of [planoMilho, planoMucuna]) {
      for (const e of p.etapas) {
        const t = textoDaEtapa(e);
        expect(t.destaques.length + t.detalhes.length).toBe(t.linhas.length);
        expect(t.destaques.length).toBeLessThanOrEqual(3);
      }
    }
  });

  it("nas respostas reais, toda etapa com dado tem de 1 a 3 destaques", () => {
    for (const e of planoMilho.etapas) {
      const t = textoDaEtapa(e);
      if (t.linhas.length > 0) {
        expect(t.destaques.length).toBeGreaterThanOrEqual(1);
        expect(t.destaques.length).toBeLessThanOrEqual(3);
      }
    }
  });

  it("Kc do milho chega em uma linha só, com vírgula decimal", () => {
    const e6 = textoDaEtapa(planoMilho.etapas[5]!);
    const kc = e6.linhas.filter((l) => l.rotulo.startsWith("Kc"));
    expect(kc).toHaveLength(1);
    expect(kc[0]!.valor).toMatch(/^inicial \d+,\d+ · médio \d+,\d+ · final/);
  });
});

describe("formatarValor", () => {
  it("cola a unidade só em número solto", () => {
    expect(formatarValor("6 a 10", "kg/ha")).toBe("6 a 10 kg/ha");
    expect(formatarValor("2", "cm")).toBe("2 cm");
    expect(formatarValor("menos de 10", "%")).toBe("menos de 10 %");
    expect(formatarValor("24 (2 anos)", "meses")).toBe("24 meses (2 anos)");
  });
  it("texto livre já traz a sua unidade: não duplica", () => {
    expect(formatarValor("40 a 80 kg/ha de P2O5, sendo 40 para solo alto", "kg/ha de P2O5")).toBe("40 a 80 kg/ha de P2O5, sendo 40 para solo alto");
    expect(formatarValor("0,80 m entre linhas x 0,20 m entre covas", "")).toBe("0,80 m entre linhas x 0,20 m entre covas");
  });
});

describe("regras do produto sobre o texto gerado a partir de respostas reais", () => {
  const todas = [planoMilho, planoMucuna].flatMap((p) => p.etapas.map((e) => ({ cultura: p.cultura, e, t: textoDaEtapa(e) })));

  it("nunca imprime null, undefined, caminho de arquivo nem nota interna", () => {
    for (const { t } of todas) {
      const txt = JSON.stringify(t);
      expect(txt).not.toMatch(/\bnull\b|undefined|file:\/\/|[A-Za-z]:\\|plano_staging|docs_rag|REVISÃO TÉCNICA|motivo_interno|\bdata\/|\.csv|\.parquet|safra_\d/);
    }
  });

  it("toda linha tem valor e, quando vem de publicação, mostra a fonte", () => {
    for (const { e, t } of todas) {
      expect(t.linhas.length).toBe(e.itens.length);
      e.itens.forEach((it, i) => {
        expect(t.linhas[i]?.valor.length).toBeGreaterThan(0);
        if (it.status === "verificado") expect(t.linhas[i]?.fonte).toBeTruthy();
      });
    }
  });

  it("adubação (etapa 7) sempre avisa que é referência da fonte", () => {
    const e7 = planoMilho.etapas.find((e) => e.numero === 7)!;
    expect(e7.itens.every((i) => i.referencia_da_fonte)).toBe(true);
    for (const l of textoDaEtapa(e7).linhas) expect(l.selos.map((s) => s.dica)).toContain(NOTA_REFERENCIA);
  });

  it("toda etapa mostra dado ou declara o que falta", () => {
    for (const { cultura, e, t } of todas) expect(t.linhas.length + t.faltas.length, `${cultura} etapa ${e.numero}`).toBeGreaterThan(0);
  });

  it("etapas 2 e 3 (motor): a 2 diz o que plantar com a época de plantio; a 3 declara que não há previsão de chuva", () => {
    const e2 = textoDaEtapa(planoMilho.etapas[1]!);
    expect(e2.linhas.length).toBeGreaterThanOrEqual(3);
    expect(e2.linhas.some((l) => /Época de plantio/.test(l.valor))).toBe(true);
    const e3 = textoDaEtapa(planoMilho.etapas[2]!);
    expect(e3.faltas.some((f) => /previsão de chuva/i.test(f))).toBe(true);
  });

  it("mucuna: pós-colheita declara que não se aplica", () => {
    const e10 = textoDaEtapa(planoMucuna.etapas[9]!);
    expect(e10.faltas.some((f) => /não se aplica/i.test(f))).toBe(true);
  });
});
