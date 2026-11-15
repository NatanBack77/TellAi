"""Antes/depois do consórcio no motor (consorcio_modo = 'sem' | 'rotulo' | 'desempate') em ~15 municípios, com clima REAL (clima_diario.parquet).

Para cada ponto x cultura atual, roda o motor 3 vezes (mesma semente) e mede:
  - quantas alternativas ganham rótulo de consórcio (par com LER publicado) e quantas ficam em lacuna;
  - se 'rotulo' muda alguma nota/faixa/alternativa (deve ser NÃO);
  - se 'desempate' muda a escolha das alternativas (só pode mudar em empate exato) e o `empate_tecnico` (não pode mudar);
  - quantos pares de alternativas em empate técnico o critério secundário SEPARARIA (um com estudo, outro sem).
Separar por esse critério NÃO significa que uma alternativa seja melhor; não há LER do usuário nem produtividade.

Uso: python experimentos/ler/antes_depois.py  (1 processo; ~1-2 min)
Saída: experimentos/ler/saida/antes_depois.csv e antes_depois.json
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.culturas import consorcio  # noqa: E402
from src.culturas.ciclo import ClimaPonto  # noqa: E402
from src.culturas.motor import gerar_cenarios  # noqa: E402
from src.culturas.parametros import Parametros  # noqa: E402
from src.culturas.tabela_culturas import carregar  # noqa: E402

PONTOS = ["quixada_ce", "amontada_ce", "caridade_ce", "fortaleza_ce", "ico_ce", "ipaumirim_ce", "limoeiro_do_norte_ce", "pacajus_ce",
          "pindoretama_ce", "santana_do_acarau_ce", "crateus_ce", "mossoro_rn", "patos_pb", "petrolina_pe", "serra_talhada_pe"]
ATUAIS = ["milho", "sorgo", "feijao_caupi"]
SAIDA = RAIZ / "experimentos/ler/saida"


def _sem_consorcio(c: dict) -> str:
    return json.dumps({k: v for k, v in c.items() if k not in ("consorcio", "lacunas", "suposicoes")}, sort_keys=True, default=str)


def main():
    clima = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    tab = carregar()
    linhas, resumo = [], {"pontos": PONTOS, "atuais": ATUAIS}
    for pid in PONTOS:
        if pid not in set(clima["ponto_id"].unique()):
            print("sem clima:", pid)
            continue
        for atual in ATUAIS:
            res = {}
            for modo in ("sem", "rotulo", "desempate"):
                p = Parametros(consorcio_modo=modo)
                serie = ClimaPonto.de_dataframe(clima, pid, p.ano_ini, p.ano_fim)
                res[modo] = gerar_cenarios({"local": pid}, atual, tab, clima=serie, params=p)
            sem, rot, des = res["sem"], res["rotulo"], res["desempate"]
            alts = [c for c in rot if c["rotacao"][1] != atual]
            n_rotulo = sum(1 for c in alts if c["consorcio"]["respaldo"])
            idem_rot = all(_sem_consorcio(a) == _sem_consorcio(b) for a, b in zip(sem, rot)) and len(sem) == len(rot)
            escolha_sem = [c["rotacao"][1] for c in sem[1:]]
            escolha_des = [c["rotacao"][1] for c in des[1:]]
            emp_sem = [bool(c["faixa_incerteza"].get("empate_tecnico")) for c in sem[1:]]
            emp_des = [bool(c["faixa_incerteza"].get("empate_tecnico")) for c in des[1:]]
            sup = [bool(consorcio.tem_respaldo(atual, c["rotacao"][1])) for c in sem[1:]]
            separa = len(sup) >= 2 and len(set(sup)) > 1
            linhas.append({"ponto": pid, "atual": atual, "alternativas": "|".join(escolha_sem), "alternativas_desempate": "|".join(escolha_des),
                           "n_alt": len(alts), "n_com_rotulo": n_rotulo, "n_lacuna": len(alts) - n_rotulo, "rotulo_nao_muda_nada": idem_rot,
                           "desempate_muda_escolha": escolha_sem != escolha_des, "empate_tecnico_igual": emp_sem == emp_des,
                           "empate_tecnico_nas_alternativas": all(emp_sem) and len(emp_sem) > 0,
                           "criterio_separaria_as_alternativas": separa,
                           "faixas_ler": "; ".join(f"{c['rotacao'][1]}={c['consorcio']['respaldo']['ler_min']}-{c['consorcio']['respaldo']['ler_max']}"
                                                   for c in alts if c["consorcio"]["respaldo"])})
            print(pid, atual, escolha_sem, "rotulo:", n_rotulo, "/", len(alts), "| muda escolha:", escolha_sem != escolha_des, "| separa:", separa, flush=True)
    SAIDA.mkdir(parents=True, exist_ok=True)
    with open(SAIDA / "antes_depois.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    tot = len(linhas)
    n_alt = sum(r["n_alt"] for r in linhas)
    resumo.update({
        "execucoes_ponto_x_atual": tot, "alternativas_total": n_alt, "alternativas_com_rotulo": sum(r["n_com_rotulo"] for r in linhas),
        "alternativas_em_lacuna": sum(r["n_lacuna"] for r in linhas), "execucoes_com_ao_menos_um_rotulo": sum(1 for r in linhas if r["n_com_rotulo"]),
        "rotulo_mudou_algo": sum(1 for r in linhas if not r["rotulo_nao_muda_nada"]),
        "desempate_mudou_escolha": sum(1 for r in linhas if r["desempate_muda_escolha"]),
        "desempate_mudou_empate_tecnico": sum(1 for r in linhas if not r["empate_tecnico_igual"]),
        "execucoes_com_empate_tecnico_nas_alternativas": sum(1 for r in linhas if r["empate_tecnico_nas_alternativas"]),
        "execucoes_em_que_o_criterio_separaria_as_alternativas": sum(1 for r in linhas if r["criterio_separaria_as_alternativas"]),
        "leitura": "Separar duas alternativas por 'tem estudo de consórcio' não significa que uma seja melhor; sem estudo = lacuna."})
    (SAIDA / "antes_depois.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
