import { describe, expect, it } from "vitest";
import { dividirNegrito, entendidoUtil } from "./texto";

describe("Entendi", () => {
  it("some quando só repete a pergunta e aparece quando acrescenta", () => {
    expect(entendidoUtil("Entendi: quando devo plantar", "Quando devo plantar?")).toBeNull();
    expect(entendidoUtil("Entendi: milho, em Quixadá, no começo da chuva", "e o milho?")).toBe("milho, em Quixadá, no começo da chuva");
    expect(entendidoUtil(null, "x")).toBeNull();
  });
});

describe("negrito seguro", () => {
  it("**x** vira negrito e o resto continua texto (nunca HTML)", () => {
    expect(dividirNegrito("Plante **milho** agora <b>x</b>")).toEqual([
      { texto: "Plante ", negrito: false },
      { texto: "milho", negrito: true },
      { texto: " agora <b>x</b>", negrito: false },
    ]);
  });
});
