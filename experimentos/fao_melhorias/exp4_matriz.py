"""Experimento 4: o que as publicações FAO sobre rotação/agricultura de conservação acrescentam à matriz 'anterior -> seguinte'.

Só entram pares em que o texto traz a SEQUÊNCIA específica entre duas das 16 culturas. Cada evidência é conferida: o trecho
(espaços colapsados) tem de existir literalmente numa página do documento FAO baixado. NÃO altera data/culturas/matriz_rotacao.csv.
Uso: python -m experimentos.fao_melhorias.exp4_matriz   (baixa os PDFs para experimentos/fao_melhorias/.cache se faltarem)
"""
from __future__ import annotations

import csv
import hashlib
import re
import subprocess
from pathlib import Path

import pandas as pd

from experimentos.fao_melhorias import comum as C

CACHE = Path(__file__).parent / ".cache"
DOCS = {
    "icm12": ("https://www.fao.org/fileadmin/user_upload/agp/icm12.pdf",
              "FAO ICM Vol.12 (2010) Green manure/cover crops and crop rotation in Conservation Agriculture on small farms",
              "Paraguai (Regiao Oriental; Estacao Experimental Chore), subtropical, NAO semiarido"),
    "bol72": ("https://www.fao.org/4/v9926e/v9926e06.htm",
              "FAO Soils Bulletin 72 Sustainable dryland cropping in relation to soil productivity, cap. 4 Sustainable crop rotations",
              "terras secas tropicais/subtropicais (Africa Ocidental, Australia, Asia); texto de revisao"),
}
T6 = "Table 6 Weed infestation in plots of cotton sown after different species of summer green manure/cover crops, and in the check plot without a GMCC (60 days after sowing)"
T15 = ("First Corn / Grey-seeded mucuna Grey-seeded mucuna continues Second Cotton and/or Sesame Black oats + White lupine + Oilseed radish "
       "Third Cassava / Jack bean Cassava continues Fourth Corn / Grey-seeded mucuna Grey-seeded mucuna continues")
T18 = ("First Corn + Pigeon pea Pigeon pea continues Second Corn + Grey-seeded mucuna Grey-seeded mucuna continues "
       "Third Cotton or Cassava + Jack bean")
T6_LIN = {"guandu": "Pigeon pea 518 19 15 85", "feijao_de_porco": "Jack bean 382 14 3 97", "crotalaria_juncea": "Sunnhemp 191 7 9 91",
          "mucuna": "Black-seeded mucuna 300 11 7 93", "feijao_caupi": "Cowpea var. Tup"}
SEM_GMCC = "Without GMCC 2.676 100 19 81"
ALG950 = "when cotton production after corn/mucuna was compared to that obtained in the conventional systems used by farmers, there was an increase of approximately 950 kg/ha (average of 3 years of study)"
B72 = "Millet and sorghum yields are generally higher when grown the year following a grain legume."
B72_CAUPI = "legumes such as cowpea in rotation with millet have little effect on the millet yields if phosphorus fertilizer is not added"
B72_AMENDOIM = "There is substantial evidence showing relatively small residual nitrogen benefits from groundnuts and soybeans."


def baixar(doc):
    url = DOCS[doc][0]
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (doc + (".pdf" if url.endswith(".pdf") else ".htm"))
    if not f.exists():
        subprocess.run(["curl", "-sL", "-m", "180", "-A", "Mozilla/5.0", "-o", str(f), url], check=True)
    return f


def paginas(doc) -> list[str]:
    f = baixar(doc)
    if f.suffix == ".htm":
        t = re.sub(r"(?s)<[^>]+>", " ", f.read_text(encoding="latin-1"))
        import html
        return [re.sub(r"\s+", " ", html.unescape(t))]
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(f)], capture_output=True, text=True).stdout).group(1))
    out = []
    for p in range(1, n + 1):
        out.append(re.sub(r"\s+", " ", subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", str(f), "-"],
                                                      capture_output=True, text=True).stdout))
    return out


def evidencias():
    """[(anterior, seguinte, grau, criterio, doc, [trechos], ressalva, tipo)]"""
    E = []
    cf = "Medida em campo (parcelas), mas Paraguai; adubo verde como cobertura, nao lavoura de grao."
    for c, lin in T6_LIN.items():
        E.append((c, "algodao", "favoravel", "plantas_daninhas", "icm12", [T6, lin, SEM_GMCC],
                  "Algodao semeado sobre este adubo verde teve infestacao relativa menor que a parcela sem adubo verde (ver coluna 'relative %': testemunha 100). " + cf,
                  "artigo_campo_outra_regiao"))
    E.append(("mucuna", "algodao", "favoravel", "produtividade_seguinte", "icm12", [ALG950],
              "Aumento de ~950 kg/ha de algodao no sistema plantio direto com milho/mucuna vs sistema convencional do agricultor (media de 3 anos): efeito CONFUNDIDO com plantio direto; Paraguai.",
              "artigo_campo_outra_regiao"))
    seq15 = [("milho", "algodao"), ("milho", "gergelim"), ("mucuna", "algodao"), ("mucuna", "gergelim"), ("algodao", "mandioca"),
             ("gergelim", "mandioca"), ("algodao", "feijao_de_porco"), ("gergelim", "feijao_de_porco"), ("mandioca", "milho"),
             ("mandioca", "mucuna"), ("feijao_de_porco", "milho"), ("feijao_de_porco", "mucuna")]
    for a, b in seq15:
        E.append((a, b, "neutro", "sequencia_proposta", "icm12", [T15],
                  "Rotacao de 3-4 anos PROPOSTA pelos autores para solos moderadamente ferteis (Tabela 15); sem efeito medido. 'Corn / Grey-seeded mucuna' = consorcio no mesmo ano.",
                  "recomendacao_tecnica"))
    seq18 = [("guandu", "mucuna"), ("milho", "mandioca"), ("mucuna", "algodao"), ("mucuna", "mandioca"), ("mucuna", "feijao_de_porco"),
             ("milho", "algodao"), ("guandu", "milho")]
    for a, b in seq18:
        E.append((a, b, "neutro", "sequencia_proposta", "icm12", [T18],
                  "Rotacao de 3 anos PROPOSTA para recuperar solo extremamente degradado (Tabela 18); sem efeito medido; consorcios 'Corn + Pigeon pea', 'Corn + mucuna', 'Cassava + Jack bean'.",
                  "recomendacao_tecnica"))
    for a in ("feijao_comum", "amendoim"):
        for b in ("milheto", "sorgo"):
            E.append((a, b, "favoravel" if a == "feijao_comum" else "neutro", "produtividade_seguinte", "bol72",
                      [B72] + ([B72_AMENDOIM] if a == "amendoim" else []),
                      "Afirmacao GERAL sobre 'grain legume' -> milheto/sorgo (classe, nao a cultura nominal)"
                      + ("; o mesmo texto diz que o beneficio residual de N do amendoim e relativamente pequeno (por isso neutro)." if a == "amendoim" else "; 'os efeitos beneficos sao um tanto contestados' segundo o proprio texto."),
                      "revisao"))
    E.append(("feijao_caupi", "milheto", "neutro", "produtividade_seguinte", "bol72", [B72_CAUPI],
              "Condicional: caupi em rotacao com milheto tem pouco efeito sobre o milheto se nao houver adubacao fosfatada (Fussell 1992, citado). Em PAR JA FAVORAVEL na matriz (sanidade): este trecho acrescenta ressalva, nao novo par.",
              "revisao"))
    return E


def main():
    paginas_doc = {d: paginas(d) for d in DOCS}
    E = evidencias()
    linhas, falhas = [], []
    for a, b, grau, crit, doc, trechos, res, tipo in E:
        pg = None
        for t in trechos:
            tn = re.sub(r"\s+", " ", t)
            achou = [i + 1 for i, p in enumerate(paginas_doc[doc]) if tn in p]
            if not achou:
                falhas.append((a, b, t))
            elif pg is None:
                pg = achou[0]
        linhas.append(dict(anterior=a, seguinte=b, grau_proposto=grau, criterio=crit, url=DOCS[doc][0], documento=DOCS[doc][1],
                           pagina_pdf=pg if DOCS[doc][0].endswith(".pdf") else "HTML cap.4", trecho=" || ".join(trechos),
                           tipo_evidencia=tipo, regiao_estudo=DOCS[doc][2], ressalva=res,
                           trecho_conferido_na_pagina=(pg is not None and not any(f[0] == a and f[1] == b for f in falhas))))
    out = C.SAIDA / "exp4_matriz_candidata_fao.csv"
    pd.DataFrame(linhas).to_csv(out, index=False)
    m = pd.read_csv(C.RAIZ / "data/culturas/matriz_rotacao.csv")
    ja = {(r.anterior, r.seguinte) for r in m.itertuples() if r.grau != "LACUNA" and r.anterior != r.seguinte}
    df = pd.DataFrame(linhas)
    pares = {(r.anterior, r.seguinte) for r in df.itertuples() if r.trecho_conferido_na_pagina}
    novos = sorted(pares - ja)
    ids = set(m.anterior) | set(m.seguinte)
    print("falhas de conferencia:", falhas)
    print("pares da matriz atual com evidencia:", len(ja), "| pares FAO conferidos:", len(pares), "| novos (eram LACUNA):", len(novos),
          "| ja cobertos:", sorted(pares & ja))
    print("cobertura: %d/240 = %.1f%% -> %d/240 = %.1f%%" % (len(ja), 100 * len(ja) / 240, len(ja) + len(novos), 100 * (len(ja) + len(novos)) / 240))
    print("novos:", novos)
    print(df.groupby(["tipo_evidencia", "criterio"]).size())
    # pares novos por tipo
    nv = df[df.apply(lambda r: (r.anterior, r.seguinte) in set(novos), axis=1)]
    print(nv.groupby("tipo_evidencia").apply(lambda g: g[["anterior", "seguinte"]].drop_duplicates().shape[0]))
    print("pares com medicao em campo (novos):", nv[nv.tipo_evidencia == "artigo_campo_outra_regiao"][["anterior", "seguinte"]].drop_duplicates().shape[0])


if __name__ == "__main__":
    main()
