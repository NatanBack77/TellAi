import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import milho from "@/features/plano/models/fixtures/plano-milho-quixada.json";
import { planoSchema } from "@/features/plano/models/plano.model";
import type { PlanoViewModel } from "@/features/plano/viewmodels/usePlanoViewModel";
import { textoDaEtapa } from "@/features/plano/viewmodels/textoEtapa";
import { ConteudoEtapa } from "./ConteudoEtapa";

const plano = planoSchema.parse(milho);

function vm(numero: number): PlanoViewModel {
  return {
    semLocal: false,
    culturaNome: plano.cultura_nome,
    culturaExemplo: true,
    carregando: false,
    erro: false,
    texto: textoDaEtapa(plano.etapas.find((e) => e.numero === numero)!),
    aviso: plano.aviso,
    limites: plano.limites,
    tentarDeNovo: () => undefined,
  };
}

const PROIBIDO = /sem dado|n[ãa]o temos|ainda n[ãa]o h[áa]|n[ãa]o coletado|ainda sem/i;

describe("ConteudoEtapa: nunca mostra o que não temos", () => {
  it("em nenhuma das 10 etapas aparece aviso de falta de dado", () => {
    for (const e of plano.etapas) {
      const { container, unmount } = render(<ConteudoEtapa plano={vm(e.numero)} municipio="Quixadá" />);
      expect(container.textContent, `etapa ${e.numero}`).not.toMatch(PROIBIDO);
      unmount();
    }
  });

  it("etapa sem nenhum dado (milho, adubação) mostra só o encaminhamento ao técnico", () => {
    const base = vm(7);
    const vazio = { ...base, texto: { ...base.texto!, linhas: [], destaques: [], detalhes: [], semDados: true } };
    render(<ConteudoEtapa plano={vazio} municipio="Quixadá" />);
    expect(screen.getByText(/converse com o técnico local/i)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(PROIBIDO);
  });

  it("não há seletor de cultura: o plano segue pela planta mais indicada e diz qual é, sem chamar de exemplo", () => {
    render(<ConteudoEtapa plano={vm(5)} municipio="Quixadá" />);
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByText(/Plano para/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/exemplo/i);
  });

  it("etapa com dado mostra a resposta objetiva e a fonte", () => {
    render(<ConteudoEtapa plano={vm(5)} municipio="Quixadá" />);
    expect(screen.getByLabelText("Resposta objetiva")).toBeTruthy();
    expect(document.body.textContent).toMatch(/Fonte: /);
  });
});
