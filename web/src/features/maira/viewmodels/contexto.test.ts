import { describe, expect, it, vi } from "vitest";
import type { Perfil } from "@/features/onboarding/models/perfil.model";
import { montarContexto, resumoDoContexto } from "./contexto";

const perfil = (p: Partial<Perfil> = {}): Perfil => ({
  versao: 2,
  municipio: { ponto_id: "quixada_ce", nome: "Quixadá (CE)" },
  solo: "medio",
  clima: "semiarido",
  concluidoEm: "2026-11-15T12:00:00Z",
  ...p,
});

describe("contexto que a Maíra recebe", () => {
  it("junta município, solo e clima que a pessoa informou", () => {
    expect(montarContexto(perfil())).toEqual({ pontoId: "quixada_ce", municipio: "Quixadá (CE)", textura: "médio", clima: "Semiárido" });
  });

  it("converte o solo para o formato da API (com acento e 'não sei')", () => {
    expect(montarContexto(perfil({ solo: "arenoso" })).textura).toBe("arenoso");
    expect(montarContexto(perfil({ solo: "argiloso" })).textura).toBe("argiloso");
    expect(montarContexto(perfil({ solo: "nao_sei" })).textura).toBe("não sei");
  });

  it("a frase 'o que a Maíra já sabe' cita local, solo e clima", () => {
    expect(resumoDoContexto(montarContexto(perfil())).join(" · ")).toBe("Quixadá (CE) · solo médio · clima semiárido");
    expect(resumoDoContexto(montarContexto(perfil({ solo: "nao_sei" })))[1]).toBe("solo: não sei");
  });
});

describe("o que vai ao servidor", () => {
  it("manda o contexto em campos próprios e a mensagem sem alteração (sem cultura_atual)", async () => {
    const post = vi.fn().mockResolvedValue({});
    vi.resetModules();
    vi.doMock("@/shared/api/httpClient", () => ({ http: { post } }));
    const { conversaService } = await import("../services/conversa.service");
    await conversaService.enviar("Quando devo plantar?", { v: 1 }, montarContexto(perfil()));
    const [caminho, , corpo] = post.mock.calls[0]!;
    expect(caminho).toBe("/conversa");
    expect(corpo).toEqual({ mensagem: "Quando devo plantar?", estado: { v: 1 }, ponto_id: "quixada_ce", perfil: { textura: "médio" } });
    vi.doUnmock("@/shared/api/httpClient");
  });
});
