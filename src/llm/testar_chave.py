"""Teste de fumaça da chave DeepSeek: `python -m src.llm.testar_chave`.

Faz UMA chamada mínima real (só se houver DEEPSEEK_API_KEY no .env/ambiente). Imprime status, modelo, latência, tokens (`usage`) e
custo estimado a partir dos preços da doc oficial (https://api-docs.deepseek.com/quick_start/pricing, lida em 2026-11-14).
NUNCA imprime a chave. Sem chave, explica o que fazer e não chama nada.
"""
from __future__ import annotations

import sys
import time

from .ambiente import carregar_env
from .provedores import DeepSeek, ProvedorErro, ProvedorIndisponivel

# US$ por 1M tokens, deepseek-flash: (fora do pico, pico). Entrada = cache miss (limite superior), saida.
PRECO_FLASH = {"entrada": (0.15, 0.30), "saida": (0.60, 1.20)}
URL_PRECOS = "https://api-docs.deepseek.com/quick_start/pricing"


def custo_estimado(modelo: str, uso: dict | None) -> str | None:
    """Faixa 'fora do pico .. pico' em US$, só para deepseek-flash (único preço lido). Outro modelo => None."""
    if modelo != "deepseek-flash" or not uso or uso.get("prompt_tokens") is None or uso.get("completion_tokens") is None:
        return None
    pt, ct = uso["prompt_tokens"], uso["completion_tokens"]
    f = [(pt * PRECO_FLASH["entrada"][i] + ct * PRECO_FLASH["saida"][i]) / 1e6 for i in (0, 1)]
    return f"US$ {f[0]:.6f} (fora do pico) a US$ {f[1]:.6f} (pico), sem desconto de cache; preços de {URL_PRECOS}"


def main(argv: list[str] | None = None, provedor: DeepSeek | None = None, saida=print) -> int:
    carregar_env()
    prov = provedor or DeepSeek()
    if not prov._chave:
        saida("Sem chave: nenhuma chamada foi feita.\n"
              "1) Crie a chave em https://platform.deepseek.com/api_keys\n"
              "2) No arquivo .env da raiz do projeto, preencha: DEEPSEEK_API_KEY=<sua chave> (sem aspas, sem espaço)\n"
              "3) Rode de novo: python -m src.llm.testar_chave")
        return 2
    saida(f"Chave encontrada (não será exibida). Modelo: {prov.modelo}. Chamando {prov.base_url}/chat/completions ...")
    t0 = time.perf_counter()
    try:
        texto = prov.gerar("", "diga ok", max_tokens=5)
    except ProvedorIndisponivel as e:
        saida(f"Indisponível: {e}")
        return 2
    except ProvedorErro as e:
        saida(f"FALHA: {e}")
        return 1
    seg = time.perf_counter() - t0
    saida(f"Status: OK (HTTP 200)\nModelo: {prov.modelo}\nLatência: {seg:.2f} s\nResposta (máx. 5 tokens): {texto.strip()[:60]!r}")
    u = prov.ultimo_uso
    saida(f"Tokens (usage): {u}" if u else "Tokens (usage): a resposta não trouxe o campo usage")
    c = custo_estimado(prov.modelo, u)
    saida(f"Custo estimado: {c}" if c else f"Custo estimado: não calculado (a doc lida só dá preço do modelo 'deepseek-flash'; veja {URL_PRECOS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
