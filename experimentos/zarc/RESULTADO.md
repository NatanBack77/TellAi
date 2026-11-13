# ZARC no motor de culturas (2026-11-13)

Dados: `data/processed/zarc_ce.parquet` (108.818 linhas CE; 184 municípios; 53 culturas; manejo sequeiro = 72.630 linhas) e
`zarc_manifesto.json` (URLs, sha256, data). Fonte: dados.agricultura.gov.br, Tábua de Risco, CC BY. Safras 2024/25, 2025/26, 2026/27
e "perene, olerícola e sem safra".

## Leitura dos dados (observada; o dicionário oficial não define)
`decN` ∈ {0, 20, 30, 40}: 0 = sem indicação; 20/30/40 = nível de risco máximo em que o plantio é indicado. Permitido ao risco r se 0 < decN ≤ r.

## Integração (`src/culturas/zarc.py`, `Parametros.usar_zarc`, padrão DESLIGADO)
Início de plantio fora dos decêndios permitidos recebe nota 0 (NaN segue NaN). Cultura sem ZARC no município NÃO é restringida e vira lacuna.
Mapeadas (nome claro): algodão, amendoim, feijão-caupi, feijão comum (→ "Feijão 2ª Safra", única entrada de sequeiro no CE; suposição),
gergelim, girassol, mamona, mandioca, milheto, milho (1ª safra), palma. Sem ZARC: crotalária, feijão-de-porco, guandu, mucuna (adubação verde)
e sorgo (granífero × forrageiro é ambíguo).
Suposições a decidir pelo usuário: nível de risco (padrão 30), solo ("qualquer" = algum solo indica; "todos" = conservador), safra mais recente.

## Comparação sem × com ZARC (10 municípios do CE, milho como cultura atual; `comparar.py`, `comparacao.json`)
- **Janela de plantio muda muito.** Sem ZARC o motor sugere plantio em nov–dez (milho em 17/12, mandioca em 18/10–28/10); com ZARC as janelas
  caem em jan–mar (milho 31/01–20/02), coerente com a quadra chuvosa do CE. O ZARC corrige uma fraqueza do motor (só clima médio do ciclo).
- **Viabilidade quase não muda** em 7 de 10 municípios; perdem culturas: Fortaleza (palma), Ipaumirim (girassol), Limoeiro do Norte
  (algodão, girassol, mandioca: 14 → 11).
- Limites: ZARC mede risco de perda de produtividade por clima; não substitui técnico local. A janela depende do nível de risco e da
  suposição de solo; não há validação com ciclo real ainda.
