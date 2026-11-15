"""Calendário VERIFICADO mês x cultura por município (15 do CE): ZARC (risco 20/30/40, sequeiro, solo) x motor de ciclo x PAM x FAO/EcoCrop.
Saída (experimentos/calendario_solo/saida/): calendario_zarc_longo.csv (município x cultura x mês), calendario_resumo.csv (uma linha por
município x cultura), inconsistencias.csv, leitura_dec.json, e uma tabela mês x cultura por município em calendario_<municipio>.csv.
Rodar: .venv/bin/python experimentos/calendario_solo/calendario.py  (1 processo; ~2 min)."""
import json, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from src.app import mvp as M
from src.culturas import zarc as Z
from src.culturas.parametros import Parametros
from src.culturas.motor import avaliar_local

SAIDA = RAIZ / "experimentos/calendario_solo/saida"; SAIDA.mkdir(exist_ok=True)
REGIAO = {"fortaleza": "litoral", "aracati": "litoral/Jaguaribe", "itapipoca": "litoral", "camocim": "litoral", "quixada": "sertão central", "taua": "Inhamuns",
          "quixeramobim": "sertão central", "crateus": "sertão/Crateús", "crato": "Cariri", "barbalha": "Cariri", "tiangua": "Ibiapaba", "ibiapina": "Ibiapaba",
          "limoeiro_do_norte": "Jaguaribe", "russas": "Jaguaribe", "ico": "Centro-Sul/Jaguaribe"}
MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PAM = {"milho": ["Milho (em grão)"], "feijao_caupi": ["Feijão (em grão)"], "feijao_comum": ["Feijão (em grão)"], "sorgo": ["Sorgo (em grão)"],
       "mandioca": ["Mandioca"], "algodao": ["Algodão herbáceo (em caroço)"], "amendoim": ["Amendoim (em casca)"], "girassol": ["Girassol (em grão)"],
       "mamona": ["Mamona (baga)"], "gergelim": ["Gergelim"]}   # sem PAM no arquivo: milheto, guandu, palma, crotalária, feijão-de-porco, mucuna
PAM_AGREGADO = {"feijao_caupi": "PAM 'Feijão (em grão)' soma caupi e comum (não separa)", "feijao_comum": "PAM 'Feijão (em grão)' soma caupi e comum (não separa)"}
ZARC_SORGO = ("sorgo granifero", "sorgo forrageiro", "sorgo granifero 2a safra", "sorgo forrageiro 2a safra")   # no ZARC, mas NÃO mapeado pelo motor

tab = M.carregar_tabela(); cult = list(tab)
pontos = pd.read_csv(RAIZ / "data/processed/pontos.csv").set_index("ponto_id")
pam = pd.read_parquet(RAIZ / "data/processed/pam_ce.parquet")
pam = pam[(pam.variavel == "area_colhida_ha") & (pam.ano.between(2021, 2023))]

def meses(v):  # decêndio (36 bool) -> nº de decêndios permitidos por mês (convenção 3 por mês)
    return np.asarray(v, int).reshape(12, 3).sum(axis=1)

def faixa(m3):  # texto 'fev-mai' dos meses com ao menos 1 decêndio
    ms = [i for i in range(12) if m3[i] > 0]
    return "—" if not ms else ",".join(MES[i] for i in ms)

zraw = pd.read_parquet(RAIZ / "data/processed/zarc_ce.parquet"); zraw = zraw[zraw.Cod_Outros_Manejos == 1]
zraw = zraw.assign(_n=zraw.Nome_cultura.map(Z._norm))
vals = sorted(set(np.unique(zraw[Z.DEC].to_numpy())))
json.dump({"valores_distintos_dec_sequeiro": [int(x) for x in vals], "linhas_sequeiro": int(len(zraw)),
           "dicionario": "MAPA dicionario-de-dados-tabua-de-risco-2026.pdf: 'dec1 a dec36 = Periodo de plantio no ano separado por decendios de 1 a 36'; NAO define 0/20/30/40 (leitura 0=sem indicacao, 20/30/40=risco maximo vem das portarias/observacao).",
           "mes_do_decendio": "convencao 3 decendios por mes (dec1-3 jan ... dec34-36 dez); o dicionario nao define"}, open(SAIDA / "leitura_dec.json", "w"), ensure_ascii=False, indent=1)

long_, resumo, incons = [], [], []
for m, reg in REGIAO.items():
    pid = m + "_ce"; geo = int(pontos.loc[pid, "ibge"]); cl = M.clima_ponto(pid)
    av_off = avaliar_local(tab, cl, Parametros(usar_zarc=False, n_sorteios=100))["culturas"]
    av_on = avaliar_local(tab, cl, Parametros(usar_zarc=True, n_sorteios=100))["culturas"]
    for c in cult:
        jr = {r: Z.janela(geo, c, r, "qualquer") for r in (20, 30, 40)}
        tem = jr[30]["permitido"] is not None
        arr = {r: (meses(jr[r]["permitido"]) if tem else None) for r in (20, 30, 40)}
        solos = {s: Z.janela(geo, c, 30, s) for s in ("arenoso", "medio", "argiloso")} if tem else {}
        arrs = {s: (meses(j["permitido"]) if j["permitido"] is not None and not j.get("aviso") else None) for s, j in solos.items()}
        for i in range(12):
            long_.append({"ponto_id": pid, "regiao": reg, "cultura": c, "mes": MES[i], "zarc_dec_r20": int(arr[20][i]) if tem else None,
                          "zarc_dec_r30": int(arr[30][i]) if tem else None, "zarc_dec_r40": int(arr[40][i]) if tem else None,
                          **{f"zarc_dec_r30_{s}": (int(a[i]) if a is not None else None) for s, a in arrs.items()}})
        # motor
        def mes_do(av):
            r = av[c]["res"]; return None if not r else (int(r["inicio"][3:5]), r["inicio"], r["decendio"], av[c]["estado"])
        mo, mz = mes_do(av_off), mes_do(av_on)
        ci = (av_on[c]["av"] or {}).get("ciclo_info") or {}
        # PAM
        area = None; pam_nome = ""
        if c in PAM:
            s = pam[(pam.ibge == geo) & pam["produto"].isin(PAM[c])].groupby("ano").valor.sum(min_count=1)
            area = float(s.reindex([2021, 2022, 2023]).mean()) if s.notna().any() else 0.0
            pam_nome = "; ".join(PAM[c])
        # sorgo no ZARC (referência)
        zs = ""
        if c == "sorgo":
            sub = zraw[(zraw.geocodigo == geo) & zraw._n.isin(ZARC_SORGO) & (zraw.Cod_Solo.isin([1, 2, 3]))]
            if len(sub):
                X = sub[Z.DEC].to_numpy(float); X = np.where((X > 0) & (X <= 30), 1, 0).max(axis=0)
                zs = faixa(meses(X))
        mz_ok = None
        if tem and mo:  # mês do motor SEM ZARC dentro da janela do ZARC (risco 30)?
            dec_ini = min(int(mo[2]) - 1, 35); mz_ok = bool(jr[30]["permitido"][dec_ini])
        resumo.append({"ponto_id": pid, "regiao": reg, "cultura": c, "zarc": "sim" if tem else "sem ZARC", "zarc_recurso": jr[30].get("recurso") if tem else "",
                       "zarc_meses_r20": faixa(arr[20]) if tem else "", "zarc_meses_r30": faixa(arr[30]) if tem else "", "zarc_meses_r40": faixa(arr[40]) if tem else "",
                       "zarc_n_dec_r30": int(jr[30]["n_decendios"]) if tem else None,
                       **{f"zarc_meses_r30_{s}": (faixa(a) if a is not None else ("sem linha p/ este solo" if tem else "")) for s, a in arrs.items()},
                       "zarc_sorgo_nao_mapeado_meses_r30": zs,
                       "motor_sem_zarc_inicio": mo[1] if mo else "", "motor_sem_zarc_estado": mo[3] if mo else "",
                       "motor_com_zarc_inicio": mz[1] if mz else "", "motor_com_zarc_estado": mz[3] if mz else "",
                       "motor_sem_zarc_dentro_do_zarc_r30": mz_ok, "ciclo_dias": ci.get("dias"), "ciclo_fonte": ci.get("fonte"), "ciclo_regiao_fao": ci.get("regiao") or ci.get("linha"),
                       "ecocrop_ciclo_min_max": str(ci.get("ecocrop_min_max")), "pam_area_ha_2021_23_media": area, "pam_produto": pam_nome,
                       "pam_nota": PAM_AGREGADO.get(c, "" if c in PAM else "cultura ausente do arquivo PAM do projeto (tabela 1612, lavouras temporárias)")})
        r = resumo[-1]
        if c in PAM and area is not None and area > 0 and not tem:
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "PAM tem área, cultura sem ZARC", "detalhe": f"{area:.0f} ha/ano (2021-23)"})
        if c in PAM and tem and jr[30]["n_decendios"] == 0 and (area or 0) > 0:
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "ZARC sem indicação (risco 30) mas PAM tem área", "detalhe": f"{area:.0f} ha/ano"})
        if c in PAM and tem and (area or 0) == 0 and jr[30]["n_decendios"] > 0:
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "ZARC indica plantio mas PAM sem área registrada (não prova que não planta: traço/omitido = NaN)", "detalhe": f"{jr[30]['n_decendios']} decêndios"})
        if mz_ok is False and mo and mo[3] == "viavel":
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "motor SEM ZARC sugere início fora do ZARC (risco 30)", "detalhe": f"início {mo[1]} (dec {mo[2]}); ZARC permite {faixa(arr[30])}"})
        if not tem:
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "sem ZARC (janela aproximada pelas anuais quando ZARC ligado)", "detalhe": r["zarc_sorgo_nao_mapeado_meses_r30"] and f"ZARC de sorgo existe (não mapeado): {r['zarc_sorgo_nao_mapeado_meses_r30']}" or ""})
        if tem and mz and mz[3] == "viavel" and not bool(jr[30]["permitido"][min(int(mz[2]) - 1, 35)]):
            incons.append({**{k: r[k] for k in ("ponto_id", "cultura")}, "tipo": "motor COM ZARC sugere início fora do ZARC (bug?)", "detalhe": mz[1]})
    print(m, flush=True)
pd.DataFrame(long_).to_csv(SAIDA / "calendario_zarc_longo.csv", index=False)
R = pd.DataFrame(resumo); R.to_csv(SAIDA / "calendario_resumo.csv", index=False)
pd.DataFrame(incons).to_csv(SAIDA / "inconsistencias.csv", index=False)
L = pd.DataFrame(long_)
for m in REGIAO:   # tabela mês x cultura: nº de decêndios (0-3) permitidos ao risco 30, qualquer solo; vazio = sem ZARC
    t = L[L.ponto_id == m + "_ce"].pivot(index="cultura", columns="mes", values="zarc_dec_r30")[MES]
    t.to_csv(SAIDA / f"calendario_{m}.csv")
print(R.zarc.value_counts().to_dict(), len(incons))
