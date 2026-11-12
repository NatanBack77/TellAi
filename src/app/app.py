"""App SULCO (Streamlit). Iniciar: streamlit run src/app/app.py

Só lê arquivos locais (JSON/MD). Não chama API. Explicações em template, sem LLM.
Nenhum número vem do código: tudo vem dos arquivos; o que falta aparece como LACUNA.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.app import logica as L  # noqa: E402

AVISO = "Cenário a avaliar com técnico local. O app apoia a conversa; não decide e não promete que a rotação rende mais."


def lacuna(msg: str):
    st.warning(f"LACUNA: {msg}")


def pagina_limites():
    st.header("Limites dos dados")
    st.info(AVISO)
    for t in L.LIMITES_FIXOS:
        st.markdown(f"- {t}")
    st.subheader("O modelo preditivo atual")
    rel = L.ler_relatorio()
    if not rel["disponivel"]:
        lacuna(f"não foi possível ler os números do modelo ({rel['motivo']}).")
        return
    if rel["sintetico"]:
        st.error(L.ROTULO_SINTETICO + ": o relatório lido parece ser de dados sintéticos.")
    if rel["sem_ganho_no_holdout"]:
        st.error("O modelo preditivo atual NÃO supera a média histórica (climatologia) no teste de 2022-2024 "
                 f"(holdout): {', '.join(rel['sem_ganho_no_holdout'])}. "
                 "Por isso o app não usa previsão de NDVI para dar nota. Números abaixo, lidos de "
                 f"`{rel['arquivo']}`.")
    else:
        st.info(f"Nenhum modelo com skill menor ou igual a zero no holdout em `{rel['arquivo']}`; leia a tabela abaixo.")
    if rel["modelo_escolhido"]:
        st.caption(f"Modelo escolhido no relatório: {rel['modelo_escolhido']}.")
    st.markdown("**Holdout temporal** (skill acima de 0 = melhor que a média histórica)")
    st.dataframe(pd.DataFrame([m["linha"] for m in rel["holdout"]]), hide_index=True)
    if rel["cobertura"]["linhas"]:
        st.markdown("**Faixa de incerteza: quanto ela realmente cobre** (meta x observado)")
        st.dataframe(pd.DataFrame(rel["cobertura"]["linhas"], columns=rel["cobertura"]["cabecalho"]), hide_index=True)
        st.caption("Se o observado é menor que a meta, a faixa promete mais do que entrega.")


def painel_perfil(lid: str):
    st.subheader("Perfil do local (passado, dos satélites)")
    diag, caminho = L.carregar_diagnostico()
    if not diag:
        lacuna("diagnóstico do local não encontrado em data/processed/diagnostico.")
        return
    r = L.perfil_do_local(diag, lid)
    if r is None:
        lacuna(f"este local ({lid}) não está no diagnóstico.")
        return
    p = L.resumo_perfil(r)
    c1, c2, c3 = st.columns(3)
    c1.metric("Confiança do diagnóstico", p["confianca"] or L.LACUNA)
    c2.metric("Período", " a ".join(p["periodo"]) if p["periodo"] else L.LACUNA)
    c3.metric("Maior veranico (dias)", L.fmt_num(p["maior_veranico_dias"]))
    if p["confianca_nota"]:
        st.caption(p["confianca_nota"])
    st.write(f"Anos válidos: {p['anos_validos'] if p['anos_validos'] else L.LACUNA}. "
             f"Quinzena de maior verdor: {L.fmt_num(p['slot_pico'])}; de menor verdor: {L.fmt_num(p['slot_vale'])}.")
    if p["tendencias"]:
        st.dataframe(pd.DataFrame(p["tendencias"]), hide_index=True)
    else:
        lacuna("tendências não disponíveis.")
    for t in p["lacunas"]:
        st.caption(f"Lacuna: {t}")
    with st.expander("O que o satélite não enxerga"):
        for t in (p["limites"] or L.LIMITES_FIXOS):
            st.markdown(f"- {t}")
    st.caption(f"Fonte: {Path(caminho).name}")


def coluna_cenario(c: dict):
    sint = L.e_sintetico(c, c.get("_arquivo", ""))
    titulo = ("Estratégia atual: " if L.e_atual(c) else "Alternativa: ") + L.texto_rotacao(c.get("rotacao"))
    st.markdown(f"### {titulo}")
    if sint:
        st.error(L.ROTULO_SINTETICO)
    ex = L.explicar(c)
    sc = c.get("score")
    fx = L.faixa(c)
    st.metric("Pontuação (do arquivo)", L.fmt_num(sc))
    if fx:
        st.write(f"Faixa de incerteza: de {L.fmt_num(fx[0])} a {L.fmt_num(fx[1])}.")
        st.caption("A faixa é aproximada e pode ser menor que o erro real (ver Limites dos dados).")
    else:
        lacuna("faixa de incerteza ausente.")
    st.markdown("**Por quê**")
    for t in ex["por_que"]:
        st.markdown(f"- {t}")
    st.markdown("**Benefícios**")
    for t in ex["beneficios"]:
        st.markdown(f"- {t}")
    st.markdown("**Lacunas**")
    for t in ex["lacunas"] or ["Nenhuma lacuna informada no arquivo."]:
        st.markdown(f"- {t}")
    st.markdown("**Riscos para revisão local**")
    for t in ex["riscos"]:
        st.markdown(f"- {t}")
    st.markdown("**Citações**")
    trechos = [t for t in (c.get("trechos") or []) if isinstance(t, dict)]
    if not trechos:
        st.write("Sem evidência: nenhum trecho do acervo foi citado.")
    for t in trechos:
        st.markdown(f"[{t.get('n', '?')}] {t.get('arquivo', L.LACUNA)}, p. {t.get('pagina', L.LACUNA)}: "
                    f"\"{t.get('texto', L.LACUNA)}\"")


def pagina_cenarios():
    st.header("Rotação de culturas: cenários lado a lado")
    st.info(AVISO)
    cenarios, erros = L.carregar_cenarios()
    for e in erros:
        lacuna(e)
    locais = L.locais_disponiveis(cenarios)
    if not locais:
        lacuna("nenhum cenário encontrado em data/processed/cenarios. Os módulos de culturas e evidências "
               "precisam gerar os arquivos JSON.")
        diag, _ = L.carregar_diagnostico()
        if diag:
            st.caption("Há diagnóstico de locais, mas sem cenários não há comparação de rotações.")
        return
    lid = st.selectbox("Local (ponto)", list(locais), format_func=lambda k: locais[k], key="local")
    culturas = L.culturas_do_local(cenarios, lid)
    if not culturas:
        lacuna("nenhuma cultura atual registrada para este local.")
        return
    cultura = st.selectbox("Cultura atual", culturas, key="cultura")
    painel_perfil(lid)
    sel = L.selecionar(cenarios, lid, cultura)
    if len(sel) < 3:
        lacuna(f"só {len(sel)} estratégia(s) disponível(is); o mínimo é 3, incluindo a atual.")
    if not any(L.e_atual(c) for c in sel):
        lacuna("a estratégia atual não está entre os cenários.")
    for i in range(0, len(sel), 3):
        for col, c in zip(st.columns(3), sel[i:i + 3]):
            with col:
                coluna_cenario(c)


def main():
    st.set_page_config(page_title="SULCO", layout="wide")
    st.title("SULCO: da órbita ao sulco")
    pagina = st.sidebar.radio("Página", ["Cenários", "Limites dos dados"], key="pagina")
    st.sidebar.caption(AVISO)
    pagina_cenarios() if pagina == "Cenários" else pagina_limites()


main()
