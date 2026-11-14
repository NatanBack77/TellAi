"""Gera data/culturas/fao_staging.csv a partir de fontes FAO LIDAS (arquivos baixados e extraídos localmente).

NÃO altera tabela_culturas.csv nem construir_tabela.py. Entradas:
  - fontes/fao56_tabelas_11_12_22_24.json: células das Tabelas 11, 12, 22 e 24 do FAO-56 (extraídas do HTML
    https://www.fao.org/4/x0490e/x0490e0b.htm e x0490e0e.htm por um parser de <table>; células separadas por ' | ').
  - linhas literais de outros documentos FAO (copiadas do texto extraído com pdftotext; espaços repetidos colapsados).

Uso: python experimentos/fao_melhorias/construir_staging.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTES = Path(__file__).parent / "fontes"
SAIDA = RAIZ / "data/culturas/fao_staging.csv"
COLUNAS = ["cultura_id", "atributo", "valor", "unidade", "regiao_da_fonte", "fonte", "url", "pagina_tabela", "trecho",
           "mapeamento_fao", "conversao", "observacao"]

U56 = "https://www.fao.org/4/x0490e/x0490e0b.htm"
U56E = "https://www.fao.org/4/x0490e/x0490e0e.htm"
F56 = "FAO Irrigation and Drainage Paper 56 (Allen et al. 1998) Crop evapotranspiration"
CLIMA_KC = "Kc para clima sub-umido (UR min ~45%, vento 2 m/s), cultura sem estresse; NAO ajustado ao semiarido"

# FAO -> cultura nossa: (rótulo Tabela 11 | rótulo Tabela 12/22 | rótulo Tabela 24 | nível da correspondência)
MAPA = {
    "milho": ("Maize (grain)", ["Maize, Field (grain) (field corn)"], "Maize", "direta (Zea mays)"),
    "feijao_caupi": ("Green gram, cowpeas", ["Green Gram and Cowpeas"], None, "grupo: FAO junta feijão-mungo e caupi"),
    "feijao_comum": ("Beans (dry)", ["Beans, dry and Pulses"], "Beans", "direta (feijão seco; 'Beans, dry and Pulses')"),
    "sorgo": ("Sorghum", ["Sorghum", "- grain"], "Sorghum", "direta (sorgo grão)"),
    "milheto": ("Millet", ["Millet"], None, "grupo: FAO 'Millet' sem distinguir milheto (Pennisetum glaucum)"),
    "mandioca": ("Cassava", ["Cassava"], None, "direta (ano 1 e ano 2)"),
    "algodao": ("Cotton", ["Cotton"], "Cotton", "direta"),
    "amendoim": ("Groundnut", ["Groundnut (Peanut)"], "Groundnet", "direta (Tabela 24 grafa 'Groundnet')"),
    "girassol": ("Sunflower", ["Sunflower"], "Sunflower", "direta"),
    "mamona": ("Castor beans", ["Castorbean ( Ricinus )", "Castorbean (Ricinus)"], None, "direta (Ricinus)"),
    "gergelim": ("Sesame", ["Sesame"], None, "direta"),
}
SEM_FAO = {
    "guandu": "Cajanus cajan nao consta nas Tabelas 11, 12, 22 e 24 do FAO-56 (busca por 'pigeon' nos capitulos 6 e 8 sem resultado)",
    "palma_forrageira": "Opuntia nao consta nas tabelas do FAO-56 (cultura perene CAM; sem Kc/estagios na FAO-56)",
    "crotalaria_juncea": "Crotalaria nao consta nas tabelas do FAO-56 (adubo verde)",
    "feijao_de_porco": "Canavalia nao consta nas tabelas do FAO-56 (adubo verde)",
    "mucuna": "Mucuna nao consta nas tabelas do FAO-56 (adubo verde)",
}


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _num(tok):
    m = re.match(r"^\d+(?:\.\d+)?", tok.strip())
    return m.group(0) if m else None


def _faixa(tok):
    """'0.60-0.35 11' -> ('0.60','0.35'); '0.50' -> ('0.50',None); ignora nota de rodape final."""
    t = tok.strip().split(" ")[0]
    m = re.match(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", t)
    if m:
        return m.group(1), m.group(2)
    n = _num(t)
    return (n, None) if n else (None, None)


def linhas_tabela11(t11):
    """Percorre a Tabela 11 e devolve [(rotulo, [ini,dev,mid,late,total], data_plantio, regiao, trecho)]."""
    out, atual, reg_prev = [], None, None
    for r in t11[1:]:
        if len(r) == 1:      # cabecalho de grupo
            continue
        cells = r
        if len(cells) == 8:
            atual = cells[0]
            c = cells[1:]
        elif len(cells) == 7:
            c = cells
            if atual and atual.startswith("Faba"):
                pass
        elif len(cells) == 9:      # ' | - dry | 90 | ...'
            atual = f"{atual} {cells[1]}"
            c = cells[2:]
        else:
            continue
        out.append((atual, c[:5], c[5], c[6], " | ".join(r)))
    return out


def construir():
    d = json.loads((FONTES / "fao56_tabelas_11_12_22_24.json").read_text(encoding="utf-8"))
    rows = []

    def add(cid, atr, val, un, reg, fonte, url, pag, trecho, mapa, conv="", obs=""):
        rows.append(dict(cultura_id=cid, atributo=atr, valor=val, unidade=un, regiao_da_fonte=reg, fonte=fonte, url=url,
                         pagina_tabela=pag, trecho=_norm(trecho), mapeamento_fao=mapa, conversao=conv, observacao=obs))

    # ---- Tabela 11: estagios e ciclo
    t11 = linhas_tabela11(d["T11"])
    for cid, (r11, _, _, nivel) in MAPA.items():
        achou = [x for x in t11 if x[0] and (x[0] == r11 or x[0].startswith(r11 + ":"))]
        # Cassava vem como 'Cassava: year 1' e a linha seguinte 'year 2'
        if cid == "mandioca":
            achou = [x for x in t11 if x[0] in ("Cassava: year 1", "year 2")]
        for (rot, st, data, reg, trecho) in achou:
            regiao = reg or ("Tropical regions" if cid == "mandioca" else "")
            if cid == "mandioca":
                regiao = "Tropical regions (plantio: estacao chuvosa)"
            try:
                vals = [int(x) for x in st]
            except ValueError:
                continue
            soma = sum(vals[:4])
            aviso = "" if soma == vals[4] else f"AVISO: soma dos 4 estagios ({soma}) difere do Total impresso ({vals[4]}) na propria tabela da FAO"
            tag = f"{rot}; plantio {data}; {regiao}"
            for nome, v in zip(("estagio_ini_dias", "estagio_dev_dias", "estagio_mid_dias", "estagio_late_dias", "ciclo_dias_total"), vals):
                add(cid, nome, str(v), "dias", f"{regiao} (plantio {data})", F56, U56, f"Cap. 6, Tabela 11 [{tag}]",
                    "Crop | Init | Dev | Mid | Late | Total | Plant Date | Region :: " + trecho, f"{nivel}", "", aviso)
    # ---- Tabela 12: Kc
    t12 = d["T12"]
    pai = None
    kc_rows = {}
    cat_atual = None
    for r in t12[1:]:
        if len(r) == 1:
            continue
        lab = r[0] if r[0] else (r[1] if len(r) > 1 else "")
        off = 0 if r[0] else 1
        if re.match(r"^[a-p]\. ", lab):
            cat_atual = (lab, r[1 + off] if len(r) > 1 + off else "")
            continue
        vals = r[1 + off:]
        if not any(v.strip() for v in vals):      # linha-pai sem valores (ex.: 'Sorghum' antes de '- grain')
            pai = lab
            continue
        if lab.startswith("- "):
            kc_rows.setdefault(pai, []).append((cat_atual, vals, pai + " " + " | ".join(r)))
        else:
            kc_rows.setdefault(lab, []).append((cat_atual, vals, " | ".join(r)))
    t22 = {}
    pai22 = None
    for r in d["T22"][1:]:
        if len(r) == 1:
            continue
        lab = r[0] if r[0] else r[1]
        off = 0 if r[0] else 1
        vv = r[1 + off:]
        if not any(v.strip() for v in vv):
            pai22 = lab
            continue
        if lab.startswith("- "):
            t22.setdefault(pai22, []).append((vv, pai22 + " " + " | ".join(r)))
        else:
            t22.setdefault(lab, []).append((vv, " | ".join(r)))
    for cid, (_, labs, r24, nivel) in MAPA.items():
        for lab in labs:
            for (cat, vals, trecho) in kc_rows.get(lab, []):
                sub = ""
                if lab == "Cassava" or (cid == "sorgo" and "- sweet" in trecho):
                    continue
                if len(vals) < 4:
                    continue
                kini, kmid, kend, hmax = vals[0], vals[1], vals[2], vals[3]
                ini = _num(kini) if kini.strip() else cat[1]
                ctx = f"Categoria '{cat[0]}': Kc ini do grupo = {cat[1]}; " if not kini.strip() else ""
                trecho_ini = f"{cat[0]} | {cat[1]} || {trecho}" if not kini.strip() else trecho
                a, b = _faixa(kmid)
                e1, e2 = _faixa(kend)
                base = dict(regiao_da_fonte=f"{CLIMA_KC}", fonte=F56, url=U56, mapa=nivel)
                add(cid, "kc_ini", str(_num(ini) or ini), "adimensional", base["regiao_da_fonte"], F56, U56,
                    f"Cap. 6, Tabela 12 [{lab}]", "Kc ini := valor do grupo (coluna 'Kc ini' e cabecalho em imagem): " + trecho_ini, nivel, "",
                    "cabecalho da coluna Kc ini e IMAGEM (x0490e2a.gif); valor herdado do grupo, conferido com o exemplo do cap. 6 (feijao seco: 0.4, 1.15, 0.35)")
                if b:
                    add(cid, "kc_mid_min", min(a, b), "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel,
                        "faixa 'a-b' da tabela gravada em kc_mid_min/kc_mid_max", "")
                    add(cid, "kc_mid_max", max(a, b), "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel,
                        "faixa 'a-b' da tabela gravada em kc_mid_min/kc_mid_max", "")
                else:
                    add(cid, "kc_mid", a, "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel)
                if e2:
                    obs = ("nota 11 da tabela: primeiro valor = colheita com grao umido; segundo = colheita apos secagem completa no campo"
                           if cid == "milho" else "faixa da tabela; nota de rodape da FAO (colheita fresca x seca ou outra) nao usada para escolher")
                    add(cid, "kc_end_min", min(e1, e2), "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel, "", obs)
                    add(cid, "kc_end_max", max(e1, e2), "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel, "", obs)
                else:
                    add(cid, "kc_end", e1, "adimensional", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel)
                h = _faixa(hmax)
                if h[0]:
                    add(cid, "altura_max_m", h[0] if not h[1] else min(h), "m", base["regiao_da_fonte"], F56, U56, f"Cap. 6, Tabela 12 [{lab}]", trecho, nivel,
                        "" if not h[1] else "faixa: gravado o limite inferior; ver trecho")
            # mandioca: dois anos
        if cid == "mandioca":
            for lab in ("- year 1", "- year 2"):
                pass
    # mandioca (Tabela 12 tem 'Cassava' + '- year 1/2'; as linhas '- year N' tem 5 celulas)
    cass = [x for x in d["T12"] if len(x) >= 5 and x[0] == "" and x[1] in ("- year 1", "- year 2")]
    for r in cass:
        ano = r[1][-1]
        tr = "Cassava | | | | || " + " | ".join(r)
        tag = f"Cap. 6, Tabela 12 [Cassava year {ano}]"
        for nome, tok in (("kc_ini", r[2]), ("kc_mid", r[3]), ("kc_end", r[4]), ("altura_max_m", r[5])):
            add("mandioca", nome, _num(tok), "adimensional" if nome.startswith("kc") else "m", CLIMA_KC, F56, U56, tag,
                "Cassava | " + " | ".join(r), "direta (ano %s)" % ano, "", f"ano {ano} do ciclo da mandioca; nota 3: Kc mid assume cultura sem estresse durante/apos a estacao chuvosa; Kc end considera dormencia na estacao seca" if nome in ("kc_mid", "kc_end") else "")
    # ---- Tabela 22: raiz e depleção
    for cid, (_, labs, r24, nivel) in MAPA.items():
        for lab in labs + (["Cassava"] if cid == "mandioca" else []):
            for (vals, trecho) in t22.get(lab, []):
                if cid == "mandioca" or (cid == "sorgo" and "- sweet" in trecho):
                    continue
                if len(vals) < 2 or "-" not in vals[0]:
                    continue
                lo, hi = vals[0].split("-")
                tag = f"Cap. 8, Tabela 22 [{lab}]"
                reg = "Profundidade maxima efetiva da raiz em solo sem restricao (Tabela 22); p para ETc > 5 mm/dia"
                add(cid, "profundidade_raiz_m_min", lo, "m", reg, F56, U56E, tag, trecho, nivel)
                add(cid, "profundidade_raiz_m_max", hi, "m", reg, F56, U56E, tag, trecho, nivel)
                add(cid, "fracao_depleção_p".replace("ç", "c").replace("ã", "a"), _num(vals[1]), "fracao", reg, F56, U56E, tag, trecho, nivel)
    for r in d["T22"]:
        if len(r) >= 3 and r[0] == "" and r[1] in ("- year 1", "- year 2"):
            pass
    prev = None
    for r in d["T22"]:
        if r and r[0] == "Cassava":
            prev = "c"
            continue
        if prev == "c" and len(r) == 4 and r[1] in ("- year 1", "- year 2"):
            lo, hi = r[2].split("-")
            tag = f"Cap. 8, Tabela 22 [Cassava {r[1]}]"
            tr = "Cassava | " + " | ".join(r)
            reg = "Profundidade maxima efetiva da raiz em solo sem restricao (Tabela 22)"
            add("mandioca", "profundidade_raiz_m_min", lo, "m", reg, F56, U56E, tag, tr, "direta (ano %s)" % r[1][-1])
            add("mandioca", "profundidade_raiz_m_max", hi, "m", reg, F56, U56E, tag, tr, "direta (ano %s)" % r[1][-1])
            add("mandioca", "fracao_deplecao_p", r[3], "fracao", reg, F56, U56E, tag, tr, "direta (ano %s)" % r[1][-1])
        elif prev == "c" and len(r) != 4:
            prev = None
    # ---- Tabela 24: Ky (FAO 33 via FAO-56)
    t24 = {r[0]: r[1] for r in d["T24"][1:] if len(r) == 2}
    for cid, (_, _, r24, nivel) in MAPA.items():
        if r24 and r24 in t24:
            add(cid, "ky_total", re.match(r"[\d.]+", t24[r24].replace(",", ".")).group(0), "adimensional",
                "Resposta do rendimento a deficit hidrico, ciclo total (FAO 33)", F56, U56E, f"Cap. 8, Tabela 24 [{r24}]",
                f"Crop | Ky :: {r24} | {t24[r24]}", nivel + ("; 'Beans' sem especificar seco/verde" if r24 == "Beans" else ""))
    # ---- CROPWAT 8.0 (arquivo .CRO): Ky do milheto (nao consta na Tabela 24)
    add("milheto", "ky_total", "1.00", "adimensional", "Dados padrao do CROPWAT 8.0 (FAO)", "FAO CROPWAT 8.0, arquivo de cultura MILLET.CRO (instalador Inno Setup extraido sem executar)",
        "https://www.fao.org/fileadmin/user_upload/faowater/Applications/CRW8.ZIP", "cropwat80setup.exe -> crops/FAO/MILLET.CRO, 5a linha de dados",
        "MILLET | 15 25 40 25 | 0.30 1.00 0.30 | 0.30 1.20 | 0.50 0.60 0.70 | 0.40 0.60 1.25 0.80 1.00 | 1.50",
        "grupo: 'Millet'", "", "posicao do Ky total (ultimo valor da 5a linha) INFERIDA: o formato .CRO nao foi lido na documentacao; conferida contra a Tabela 24 em milho 1.25, sorgo 0.90, algodao 0.85, amendoim 0.70, girassol 0.95, feijao 1.15 (6 de 6 coincidem)")
    # ---- FAO Paper 24, Tabela 20: ETcrop sazonal (mm) -- faixas
    U24 = "https://www.fao.org/3/s8376e/s8376e.pdf"
    F24 = "FAO Irrigation and Drainage Paper 24 (Doorenbos & Pruitt 1977) Crop water requirements, Tabela 20"
    for cid, rot, lo, hi, nivel in [
        ("milho", "Maize 400 - 750", 400, 750, "direta"), ("sorgo", "Sorghum 300 -650", 300, 650, "direta (sorgo)"),
        ("algodao", "Cotton 550 - 950", 550, 950, "direta"), ("feijao_comum", "Beans 250 - 500", 250, 500, "direta ('Beans' generico)"),
        ("girassol", "Oil seeds 300 - 600", 300, 600, "CLASSE 'Oil seeds' (nao especifica girassol)"),
        ("mamona", "Oil seeds 300 - 600", 300, 600, "CLASSE 'Oil seeds' (nao especifica mamona)"),
        ("gergelim", "Oil seeds 300 - 600", 300, 600, "CLASSE 'Oil seeds' (nao especifica gergelim)")]:
        for nome, v in (("demanda_hidrica_mm_ciclo_min", lo), ("demanda_hidrica_mm_ciclo_max", hi)):
            add(cid, nome, str(v), "mm/ciclo", "global (muda com clima, duracao e epoca; ver nota da tabela)", F24, U24,
                "Tabela 20 'Approximate Range of Seasonal ETcrop in mm', PDF p.46 (OCR)", rot, nivel, "",
                "ETcrop = demanda total da cultura (nao e chuva). OCR do PDF: valores conferidos visualmente no texto extraido")
    # ---- ICM 12: biomassa e N de adubos verdes (lacunas nao fechadas, mas VALIDACAO cruzada com a tabela atual)
    UI = "https://www.fao.org/fileadmin/user_upload/agp/icm12.pdf"
    FI = "FAO Integrated Crop Management Vol. 12-2010, Green manure/cover crops and crop rotation in Conservation Agriculture on small farms"
    for cid, ln, ms, n, nome in [("guandu", "Pigeon pea 9.153 240 13 240 22", "9153", "240", "Pigeon pea"),
                                 ("feijao_de_porco", "Jack bean 7.703 246 12 433 16", "7703", "246", "Jack bean"),
                                 ("mucuna", "Black-seeded mucuna 7.500 192 10 108 21", "7500", "192", "Black-seeded mucuna")]:
        reg = "Estacao Experimental Chore, Paraguai (subtropical, NAO semiarido); cultivo consorciado com milho, MS aos ~7 meses"
        add(cid, "palha_ms_kg_ha", ms, "kg/ha de MS da parte aerea", reg, FI, UI, "Tabela 5, PDF p.24 (impressa 14)",
            "Table 5 ... Green Manure | Dry Matter (kg/ha) | N P K (kg/ha) | C/N :: " + ln, "direta", "'.' do texto e separador de milhar: 9.153 = 9153 kg/ha", "valor de BIOMASSA TOTAL aerea do adubo verde, nao 'palha de restos de colheita'")
        add(cid, "n_acumulado_parte_aerea_kg_ha", n, "kg/ha de N na MS aerea", reg, FI, UI, "Tabela 5, PDF p.24 (impressa 14)",
            "Table 5 ... Green Manure | Dry Matter (kg/ha) | N P K (kg/ha) | C/N :: " + ln, "direta", "", "N total na biomassa (inclui N do solo e N fixado; NAO e N fixado)")
    add("crotalaria_juncea", "palha_ms_kg_ha_min", "7000", "kg/ha de MS", "Paraguai, semeada em janeiro consorciada com milho", FI, UI,
        "secao 'Sunnhemp (Crotalaria juncea L.)', PDF p.35", "great biomass production (7 to 8 t/ha of dry matter when sown in January in association with corn)",
        "direta", "7 t/ha x 1000 = 7000 kg/ha", "faixa 7-8 t/ha")
    add("crotalaria_juncea", "palha_ms_kg_ha_max", "8000", "kg/ha de MS", "Paraguai, semeada em janeiro consorciada com milho", FI, UI,
        "secao 'Sunnhemp (Crotalaria juncea L.)', PDF p.35", "great biomass production (7 to 8 t/ha of dry matter when sown in January in association with corn)",
        "direta", "8 t/ha x 1000 = 8000 kg/ha", "faixa 7-8 t/ha")
    # ---- Soils and pulses, Tabela 8: N fixado (faixas)
    US = "https://openknowledge.fao.org/server/api/core/bitstreams/083a0b41-703e-4977-b50f-6cf870d22538/content"
    FS = "FAO Soils and pulses: symbiosis for life, Table 8 'Estimates of nitrogen fixed by legumes' (Wani & Lee 1992; Peoples & Crasswell 1992)"
    for cid, rot, lo, hi, nivel in [("feijao_caupi", "Cowpea 9-125", 9, 125, "direta (Cowpea)"), ("feijao_comum", "Common Bean 3-57", 3, 57, "direta"),
                                    ("guandu", "Pigeon pea 4-200", 4, 200, "direta"), ("amendoim", "Groundnut 27-206", 27, 206, "direta")]:
        for nome, v in (("n_fixado_kg_ha_min", lo), ("n_fixado_kg_ha_max", hi)):
            add(cid, nome, str(v), "kg N/ha (por ciclo/ano, nao especificado)", "varias regioes do mundo (compilacao de 1992)", FS, US,
                "Tabela 8, PDF p.76 (impressa 67)", "Crop | Nitrogen fixation (kg ha-1) :: " + rot, nivel, "",
                "faixa muito larga: fecha a lacuna formalmente, mas nao discrimina")
    add("amendoim", "n_fixado_kg_ha_min", "110", "kg N/ha", "texto de manejo do amendoim (regiao nao especificada)",
        "FAO Fertilizer and Plant Nutrition Bulletin 16, Plant nutrition for food security (Roy et al. 2006)", "https://www.fao.org/fileadmin/templates/soilbiodiversity/Downloadable_files/fpnb16.pdf",
        "secao Groundnut, Rhizobium inoculation, PDF p.263", "The groundnut-Rhizobium symbiosis can fix about 110-150 kg N/ha.", "direta", "", "difere da tabela atual (40.9 kg/ha) e da Tabela 8 (27-206)")
    add("amendoim", "n_fixado_kg_ha_max", "150", "kg N/ha", "texto de manejo do amendoim (regiao nao especificada)",
        "FAO Fertilizer and Plant Nutrition Bulletin 16, Plant nutrition for food security (Roy et al. 2006)", "https://www.fao.org/fileadmin/templates/soilbiodiversity/Downloadable_files/fpnb16.pdf",
        "secao Groundnut, Rhizobium inoculation, PDF p.263", "The groundnut-Rhizobium symbiosis can fix about 110-150 kg N/ha.", "direta", "", "difere da tabela atual (40.9 kg/ha) e da Tabela 8 (27-206)")
    # ---- lacunas explicitas
    for cid, motivo in SEM_FAO.items():
        add(cid, "ciclo/kc/estagios/raiz/ky", "", "", "", "FAO-56 Tabelas 11, 12, 22, 24", U56, "-", "", "LACUNA", "", motivo)
    return rows


def main():
    rows = construir()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} linhas -> {SAIDA}")


if __name__ == "__main__":
    main()
