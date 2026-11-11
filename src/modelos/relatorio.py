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
    L += [""] + _lacunas(r)
    return "\n".join(L) + "\n"


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
