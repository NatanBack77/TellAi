"""Gera `relatorio_modelos.md` a partir de `metricas.json` (dados reais).

Com dados sintéticos gera só um relatório de FLUXO (`SINTETICO_relatorio_modelos.md`), sem nenhuma métrica:
métricas de dados sintéticos nunca são resultado do projeto.
"""
from __future__ import annotations

import json
from pathlib import Path

MODELOS = ("climatologia", "ridge", "xgboost")


def _f(x, nd=3) -> str:
    return "—" if x is None or x != x else f"{x:.{nd}f}"


def gerar_markdown(r: dict) -> str:
    L = ["# Relatório dos modelos (SULCO)", ""]
    if r["dados_sinteticos"]:
        L += ["> **DADOS SINTÉTICOS — teste de fluxo.** Nenhuma métrica é apresentada: não são resultado do projeto.", ""]
        L += ["## Fluxo executado", f"- Features: {', '.join(r['features'])}",
              f"- Divisão: treino {r['divisao']['anos_treino'][0]}–{r['divisao']['anos_treino'][-1]}, "
              f"holdout {r['divisao']['anos_teste']}; {r['divisao']['n_folds']} folds por célula POWER",
              "- Conformal, decisão, explicação: executados sem erro.", ""]
        L += _lacunas(r)
        return "\n".join(L) + "\n"
    d = r["divisao"]
    pers = r.get("persistencia", {})
    L += [f"Configuração: persistência **{'ligada' if pers.get('usada') else 'desligada (só clima)'}**; "
          f"SMAP **{'ligado' if r.get('umidade_solo_smap', {}).get('usada') else 'desligado (opção documentada, D52)'}**. "
          f"Features: {', '.join(r['features'])}.", ""]
    L += [f"Alvo: {r['alvo']}.", "",
          f"Treino {d['anos_treino'][0]}–{d['anos_treino'][-1]}; holdout {d['anos_teste']}; "
          f"{d['n_celulas_treino']} células POWER no treino; {d['n_folds']} folds. Confiança: **{r['confianca']}** "
          f"({r['confianca_nota']}).", "", f"> {r['aviso']}", ""]
    L += ["## Métricas por fold (GroupKFold por célula)", "",
          "| Modelo | MAE | RMSE | R² | skill vs. clim. |", "|---|---|---|---|---|"]
    for n in MODELOS:
        m = r["cv_grupos"]["resumo"][n]
        L.append(f"| {n} | " + " | ".join(f"{_f(m[k]['media'])} ± {_f(m[k]['desvio'])}"
                                          for k in ("mae", "rmse", "r2", "skill_vs_climatologia")) + " |")
    sr = r["cv_grupos"]["resumo"]["xgboost"]["skill_vs_ridge"]
    L += ["", f"XGBoost vs. Ridge (skill): {_f(sr['media'])} ± {_f(sr['desvio'])}", "", "### Por fold", "",
          "| Fold | Células validação | n | " + " | ".join(f"RMSE {n}" for n in MODELOS) + " |", "|---|---|---|---|---|---|"]
    for f in r["cv_grupos"]["folds"]:
        L.append(f"| {f['fold']} | {', '.join(f['celulas_validacao'])} | {f['n_validacao']} | " +
                 " | ".join(_f(f["modelos"][n]["rmse"]) for n in MODELOS) + " |")
    L += ["", "## Holdout temporal", "", "| Modelo | MAE | RMSE | R² | skill vs. clim. |", "|---|---|---|---|---|"]
    for n in MODELOS:
        m = r["holdout_temporal"]["modelos"][n]
        L.append(f"| {n} | {_f(m['mae'])} | {_f(m['rmse'])} | {_f(m['r2'])} | {_f(m['skill_vs_climatologia'])} |")
    L += ["", "## Cobertura da faixa de incerteza (split conformal, calibração em células distintas)", "",
          "| Modelo | Meta | CV (média ponderada) | Holdout |", "|---|---|---|---|"]
    for n in MODELOS:
        for k, v in r["cv_grupos"]["conformal"][n].items():
            h = r["holdout_temporal"]["conformal"][n]["metas"][k]
            L.append(f"| {n} | {k}% | {_f(v['cobertura_media_ponderada'])} | {_f(h['cobertura'])} |")
    L += _comparativo(r)
    dec = r["decisao"]
    L += ["", "## Decisão XGBoost vs. Ridge", "", f"**Modelo: {dec['modelo']}.** {dec['motivo']}", "",
          f"- Critérios: {dec['criterio']}", f"- Fração de folds com XGBoost melhor: {_f(dec['fracao_folds_xgb_melhor'], 2)}"]
    if dec.get("aviso"):
        L.append(f"- **Atenção:** {dec['aviso']}")
    if dec["criterio_aprovado_pelo_usuario"]:
        L.append("- Critério aprovado pelo usuário antes da avaliação com dados reais.")
    else:
        L.append("- **O critério ainda não foi aprovado pelo usuário.**")
    L += ["", "## Explicação (só explicativa, não valida)", ""]
    for k, v in r["explicacao"]["importancia_media_abs"].items():
        L.append(f"- {k}: {_f(v, 4)}")
    L += _sensibilidade(r)
    L += [""] + _lacunas(r)
    return "\n".join(L) + "\n"


ROTULOS_COMP = (("so_clima_todas_as_linhas", "só clima (modelo anterior, todas as linhas)"),
                ("so_clima_mesmas_linhas", "só clima (mesmas linhas da persistência)"),
                ("com_persistencia", "com persistência (produção)"))


def _comparativo(r: dict) -> list[str]:
    c = r.get("comparativo")
    if not c:
        return []
    L = ["", "## Só clima × com persistência (lado a lado, holdout temporal)", "", c["nota"], "",
         "| Configuração | n treino | n teste | RMSE clim. | RMSE Ridge | skill Ridge | RMSE XGB | skill XGB | skill CV Ridge | skill CV XGB |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for k, nome in ROTULOS_COMP:
        x = c[k]
        h = x["holdout"]
        L.append(f"| {nome} | {x['n_treino']} | {x['n_teste']} | {_f(h['climatologia']['rmse'], 4)} | "
                 f"{_f(h['ridge']['rmse'], 4)} | {_f(h['ridge']['skill_vs_climatologia'])} | "
                 f"{_f(h['xgboost']['rmse'], 4)} | {_f(h['xgboost']['skill_vs_climatologia'])} | "
                 f"{_f(x['cv_skill_vs_climatologia']['ridge'])} | {_f(x['cv_skill_vs_climatologia']['xgboost'])} |")
    anos = sorted(c["com_persistencia"]["holdout_por_ano"])
    L += ["", "Skill por ano do holdout (vs. climatologia do próprio conjunto):", "",
          "| Configuração | Modelo | " + " | ".join(anos) + " |", "|---|---|" + "---|" * len(anos)]
    for k, nome in ROTULOS_COMP:
        for m in ("ridge", "xgboost"):
            L.append(f"| {nome} | {m} | " + " | ".join(
                _f(c[k]["holdout_por_ano"][a][m]["skill_vs_climatologia"]) for a in anos) + " |")
    L += ["", "Cobertura conformal real no holdout (recalibrada por células como antes; **não ajustada**):", "",
          "| Configuração | Modelo | 80% (real) | 90% (real) | CV 80% | CV 90% |", "|---|---|---|---|---|---|"]
    for k, nome in ROTULOS_COMP:
        x = c[k]
        for m in ("climatologia", "ridge", "xgboost"):
            ch, cv = x["conformal_holdout"][m], x["conformal_cv"][m]
            L.append(f"| {nome} | {m} | {_f(ch['80']['cobertura'])} | {_f(ch['90']['cobertura'])} | "
                     f"{_f(cv['80'])} | {_f(cv['90'])} |")
    return L


def _sensibilidade(r: dict) -> list[str]:
    s = r.get("sensibilidade_cenarios")
    if not s:
        return []
    L = ["", "## Sensibilidade a cenários, com e sem persistência (medida)", "",
         f"Base: {s['base']}. {s['leitura']}", "",
         "As features de persistência não mudam sob cenário de chuva/temperatura: o ganho vem da memória do NDVI; "
         "cenários de clima reagem pouco.", "",
         "| Modelo | Cenário (chuva x, tmax +°C) | linhas usadas / fora da faixa | variação com persistência | variação só clima | razão |",
         "|---|---|---|---|---|---|"]
    for nome, lista in s["modelos"].items():
        for e in lista:
            cen = f"x{e['fator_chuva']:g}, +{e['delta_tmax_c']:g}"
            if e.get("sem_numero"):
                L.append(f"| {nome} | {cen} | 0 / {e['n_linhas_fora_da_faixa']} | sem número (extrapolação) | | |")
                continue
            L.append(f"| {nome} | {cen} | {e['n_linhas_usadas']} / {e['n_linhas_fora_da_faixa']} | "
                     f"{_f(e['com_persistencia']['variacao'], 5)} | {_f(e['so_clima']['variacao'], 5)} | "
                     f"{_f(e['razao_com_sobre_so_clima'], 2)} |")
    return L


def _lacunas(r: dict) -> list[str]:
    return ["## Lacunas", ""] + [f"- {x}" for x in r["lacunas"]]


def gerar(caminho_metricas: str | Path, destino: str | Path | None = None) -> Path:
    caminho_metricas = Path(caminho_metricas)
    r = json.loads(caminho_metricas.read_text(encoding="utf-8"))
    nome = "SINTETICO_relatorio_modelos.md" if r["dados_sinteticos"] else "relatorio_modelos.md"
    destino = Path(destino) if destino else caminho_metricas.parent / nome
    destino.write_text(gerar_markdown(r), encoding="utf-8")
    return destino


if __name__ == "__main__":
    import sys

    print("salvo em", gerar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
