"""App SULCO (Streamlit). Iniciar: .venv/bin/streamlit run src/app/app.py

Só lê arquivos locais (data/processed/...). Não chama API de dados. Sem LLM: explicações em template.
Nenhum número vem do texto da tela: tudo vem de arquivo ou de código rodado; o que falta aparece como LACUNA.
Como usar e roteiro de demo: docs/11_MVP.md.
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.app import logica as L  # noqa: E402
from src.app import mvp as M  # noqa: E402

AVISO = M.AVISO
LOCAL_PADRAO, CULTURA_PADRAO = "quixada_ce", "milho"
AVISO_KM = ("O satélite enxerga áreas de cerca de 250 m a 50 km, não o seu talhão. Marque o município mais próximo e "
            "use o resultado como conversa com o técnico, não como veredito.")


def lacuna(msg: str):
    st.warning(f"LACUNA: {msg}")


@st.cache_resource(show_spinner="Calculando as estratégias com o clima do local...", max_entries=64)
def calcular_cache(ponto: str, cultura: str, prioridade: str) -> dict:
    return M.calcular(ponto, cultura, prioridade)


@st.cache_resource(show_spinner="Montando as rotações de 3 safras...", max_entries=64)
def rotacao_cache(ponto: str, cultura: str, prioridade: str, rot2: str, rot3: str, textura: str, mo: str, zarc: bool) -> dict:
    rot = None if rot2 == "-" or rot3 == "-" else [cultura, rot2, rot3]
    return M.calcular_rotacao(ponto, cultura, prioridade, rot, textura, mo, zarc)


@st.cache_resource(show_spinner=False, max_entries=128)
def cenario_cache(ponto: str, cultura: str, prioridade: str, fator_chuva: float, delta_t: float) -> dict:
    return M.cenario_clima(ponto, cultura, prioridade, fator_chuva, delta_t, base=calcular_cache(ponto, cultura, prioridade))


# ------------------------------------------------------------------------------------------ 1. entrada
def mapa_e_local() -> str:
    pts = M.carregar_pontos()
    ids = list(pts["ponto_id"])
    if "local" not in st.session_state or st.session_state["local"] not in ids:
        st.session_state["local"] = LOCAL_PADRAO if LOCAL_PADRAO in ids else ids[0]
    atual = st.session_state["local"]
    st.info(AVISO_KM)
    df = pts[["ponto_id", "nome", "lat", "lon"]].copy()
    df["cor"] = [[220, 60, 40, 255] if i == atual else [40, 110, 160, 150] for i in df["ponto_id"]]
    df["raio"] = [11 if i == atual else 6 for i in df["ponto_id"]]
    camada = pdk.Layer("ScatterplotLayer", data=df, id="pontos", get_position="[lon, lat]", get_fill_color="cor",
                       get_radius="raio", radius_units="pixels", pickable=True)
    vista = pdk.ViewState(latitude=float(pts["lat"].mean()), longitude=float(pts["lon"].mean()), zoom=5.6)
    deck = pdk.Deck(layers=[camada], initial_view_state=vista, tooltip={"text": "{nome}"})
    ev = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="mapa", height=380,
                         alt="Mapa com os 195 locais; clique em um ponto para escolher")
    clicado = None
    try:
        objs = (ev.selection.objects or {}).get("pontos") or []
        clicado = objs[0].get("ponto_id") if objs else None
    except (AttributeError, KeyError, IndexError):
        clicado = None
    if clicado and clicado in ids and clicado != st.session_state.get("_ultimo_clique"):
        st.session_state["_ultimo_clique"] = clicado
        if clicado != atual:
            st.session_state["local"] = clicado
            st.rerun()
    st.caption("Clique num ponto do mapa ou use a lista abaixo (sem internet o mapa pode ficar sem fundo; os pontos aparecem).")
    nomes = dict(zip(pts["ponto_id"], pts["nome"]))
    return st.selectbox("Município / local (195 pontos; 184 do Ceará)", ids, format_func=lambda k: nomes[k], key="local")


def entradas() -> tuple[str, str, str]:
    st.subheader("1. Onde, o que você planta hoje e o que importa mais")
    lid = mapa_e_local()
    c1, c2 = st.columns(2)
    culturas = M.culturas_disponiveis()
    if st.session_state.get("cultura") not in culturas:
        st.session_state["cultura"] = CULTURA_PADRAO
    cultura = c1.selectbox("Cultura atual (lista da tabela de culturas)", list(culturas), format_func=lambda k: culturas[k],
                           key="cultura")
    prio = c2.radio("O que importa mais para você?", list(M.PRIORIDADES), format_func=lambda k: M.PRIORIDADES[k]["rotulo"],
                    key="prioridade", index=0)
    cfg = M.PRIORIDADES[prio]
    if prio == "renda":
        lacuna(cfg["regra"])
    else:
        st.caption(f"Como a prioridade foi usada: {cfg['regra']}")
    return lid, cultura, prio


# ------------------------------------------------------------------------------------------ 2. diagnóstico
def _barras(df: pd.DataFrame, x: str, y: str, titulo: str, rotulo_y: str, formato: str = ".0%", cor="#b5651d", regra: float | None = None):
    ordem = list(df[x]) if x == "rotulo" else None
    base = alt.Chart(df, title=titulo).mark_bar(color=cor).encode(
        x=alt.X(f"{x}:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=-60)),
        y=alt.Y(f"{y}:Q", title=rotulo_y, axis=alt.Axis(format=formato)),
        tooltip=[alt.Tooltip(f"{x}:N", title="Quinzena"), alt.Tooltip(f"{y}:Q", title=rotulo_y, format=formato)])
    if regra is not None:
        base = base + alt.Chart(pd.DataFrame({"r": [regra]})).mark_rule(color="#444", strokeDash=[4, 3]).encode(y="r:Q")
    st.altair_chart(base.properties(height=220), width="stretch")


def painel_diagnostico(lid: str, cultura: str, calc: dict):
    d = M.diagnostico_local(lid)
    nome = M.carregar_pontos().set_index("ponto_id").loc[lid, "nome"]
    st.subheader(f"2. O que os satélites mostram em {nome}")
    if d is None:
        lacuna(f"diagnóstico do local não encontrado em data/processed/diagnostico para {lid}.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Confiança do diagnóstico", d["confianca"] or M.LACUNA)
    c2.metric("Período do clima", " a ".join(d["periodo"]) if d["periodo"] else M.LACUNA)
    av = d["anos_validos"]
    c3.metric("Anos de NDVI aproveitáveis", av.get("ndvi", M.LACUNA))
    if d["confianca"] == "baixa":
        st.error("Confiança BAIXA: poucos anos de verdor aproveitáveis neste local. Trate tudo abaixo com muita cautela.")
    st.caption(f"{d['confianca_nota']}. Anos válidos: NDVI {av.get('ndvi', M.LACUNA)}, chuva {av.get('chuva', M.LACUNA)}, "
               f"umidade do solo {av.get('umidade_solo', M.LACUNA)} (SMAP existe só desde 2015).")

    st.markdown("#### Quando o campo costuma ficar nu")
    if d["solo_nu"]:
        st.write(d["solo_nu"]["frase"])
        _barras(d["solo_nu"]["df"], "rotulo", "frac_anos_solo_nu", "Em que fração dos anos a quinzena ficou com NDVI baixo",
                "fração dos anos", regra=0.5)
        st.caption("A linha tracejada é o corte de 50% dos anos que define a época 'típica' (regra do app, ajustável em config.yaml).")
    else:
        lacuna("solo nu não calculado para este local.")

    st.markdown("#### Quando a vegetação mais sofre")
    st.write(d["estresse_frase"])
    est = d["estresse_df"]
    if len(est):
        e2 = est.assign(rotulo=[M.rotulo_quinzena(int(q)) for q in est["quinzena"]]).dropna(subset=["frac_abaixo"])
        _barras(e2, "rotulo", "frac_abaixo", "Fração dos anos com verdor abaixo do normal da quinzena", "fração dos anos",
                cor="#a23b3b")

    st.markdown("#### Chuva e veranicos")
    if d["veranicos"]:
        st.write(d["veranicos"]["frase"])
    else:
        lacuna("veranicos não calculados para este local.")
    if "chuva_df" in d:
        _barras(d["chuva_df"].dropna(), "rotulo", "media_mm", "Chuva média por quinzena (NASA POWER, célula de ~50 km)", "mm",
                formato=".0f", cor="#3d7ea6")

    st.markdown(f"#### Quando a cultura atual ({M.culturas_disponiveis()[cultura]}) é mais vulnerável")
    v = M.vulnerabilidade_cultura_atual(lid, cultura, calc, d)
    for t in v["lacunas"]:
        lacuna(t)
    if "df" in v:
        if v["viabilidade"] != "viavel":
            st.error(f"Neste local a cultura atual está '{v['viabilidade']}' pelo motor (faixa de chuva/temperatura da tabela).")
        st.write(f"Melhor início de plantio nos dados: {v['melhor_inicio']} (ciclo suposto de {v['duracao']} dias). Os inícios "
                 f"com menor adequação: {', '.join(v['piores_inicios'])}.")
        graf = alt.Chart(v["df"], title="Adequação ao clima por data de início do plantio (0 a 1; média de 2001 a 2023)").mark_line(
            point=True, color="#2e7d32").encode(
            x=alt.X("inicio:N", sort=list(v["df"]["inicio"]), title="início do plantio (dd/mm)", axis=alt.Axis(labelAngle=-60)),
            y=alt.Y("adequacao_media:Q", title="adequação", scale=alt.Scale(domain=[0, 1])),
            tooltip=["inicio", alt.Tooltip("adequacao_media:Q", format=".2f"), alt.Tooltip("frac_anos_viaveis:Q", format=".0%")])
        st.altair_chart(graf.properties(height=220), width="stretch")
        if "solo_nu_no_ciclo" in v:
            partes = []
            partes.append(f"Épocas típicas de campo nu dentro do ciclo da melhor data: {M.rotulos_quinzenas(v['solo_nu_no_ciclo'])}.")
            partes.append(f"Quinzenas de maior estresse do verdor dentro do ciclo: {M.rotulos_quinzenas(v['estresse_no_ciclo'])}.")
            partes.append(f"Quinzenas da estação chuvosa dentro do ciclo: {M.rotulos_quinzenas(v['estacao_chuvosa_no_ciclo'])}.")
            st.write(" ".join(partes))
        st.caption("Adequação = o pior entre a nota de temperatura e a de chuva da cultura (faixas da tabela de culturas, "
                   "ciclo suposto no ponto médio). É uma regra do motor, não colheita medida.")

    st.markdown("#### Tendências (24 anos)")
    if d["tendencias"]:
        st.dataframe(pd.DataFrame(d["tendencias"]), hide_index=True)
        st.caption("'Sem tendência clara' = o teste (Mann-Kendall) não achou mudança segura; não quer dizer que nada muda.")
    for t in d["lacunas"]:
        st.caption(f"Lacuna do diagnóstico: {t}")
    with st.expander("O que o satélite não enxerga"):
        for t in L.LIMITES_FIXOS:
            st.markdown(f"- {t}")


# ------------------------------------------------------------------------------------------ 3. estratégias
def _nome(cid: str) -> str:
    return M.culturas_disponiveis().get(cid, cid)


def coluna_estrategia(c: dict, rotulo: str, prio: str):
    d = M.descricao_estrategia(c, prio)
    alvo = c["rotacao"][1]
    st.markdown(f"### {rotulo}: {_nome(alvo)}")
    if c["atual"]:
        st.caption("O que você planta hoje. Serve de comparação.")
    else:
        st.caption(f"Plantio seguinte à cultura atual: {_nome(c['rotacao'][0])} → {_nome(alvo)}.")
    inc = d["incerteza"]
    if inc["disponivel"]:
        for t in inc["linhas"] + inc["cobertura"]:
            st.write(t)
        if d["empatadas"]:
            st.warning(f"Empate técnico com {len(d['empatadas'])} outras culturas: os dados não separam esta das demais.")
            with st.expander("Quais estão empatadas"):
                st.write(", ".join(_nome(x) for x in d["empatadas"]))
    else:
        lacuna("faixa de incerteza não disponível para esta estratégia.")
    if d["epoca"]:
        st.write(d["epoca"])
    st.markdown("**Por quê (dados e fonte de cada critério)**")
    for x in d["criterios"]:
        if x["tem_dado"]:
            st.markdown(f"- **{M.NOME_CRITERIO[x['criterio']]}** ({M.nota_txt(x['nota'])}"
                        f"{'' if x['no_ranking'] else '; fora do ranking principal'}): {x['texto']}. {x['fonte']}; {x['evidencia']}.")
        else:
            st.markdown(f"- **{M.NOME_CRITERIO[x['criterio']]}**: LACUNA, sem dado com fonte para esta cultura.")
    with st.expander("Fontes completas dos dados"):
        for x in d["criterios"]:
            if x["tem_dado"]:
                st.markdown(f"- **{M.NOME_CRITERIO[x['criterio']]}**: {x['fonte_completa']}")
    if d["demanda"]:
        st.write(d["demanda"])
    st.markdown("**Benefícios (só o que tem dado por trás)**")
    for t in d["beneficios"]:
        st.markdown(f"- {t}")
    st.markdown("**Lacunas**")
    for t in d["lacunas"] or ["Nenhuma lacuna informada."]:
        st.markdown(f"- {t}")
    st.markdown("**Riscos para revisão local**")
    for t in d["riscos"]:
        st.markdown(f"- {t}")
    st.markdown("**Evidência do acervo**")
    if not d["trechos"]:
        st.write("Sem evidência: nenhum trecho do acervo foi citado para esta cultura.")
    else:
        st.caption("Trechos achados por busca automática no acervo (cita a cultura e um termo do critério). Podem não ser do "
                   "semiárido nem confirmar o valor da tabela: confira o PDF.")
    for t in d["trechos"]:
        txt = str(t.get("texto", M.LACUNA))
        st.markdown(f"[{t.get('n', '?')}] {t.get('arquivo', M.LACUNA)}, p. {t.get('pagina', M.LACUNA)}: "
                    f"\"{txt[:350]}{'…' if len(txt) > 350 else ''}\"")


def tabela_comparativa(cens: list[dict], prio: str):
    linhas = []
    for c in cens:
        d = M.descricao_estrategia(c, prio)
        f = c.get("faixa_incerteza") or {}
        cob = (f.get("cobertura") or {}).get("completa") or {}
        pc, pt = cob.get("peso_coberto"), cob.get("peso_total")
        j = c.get("janela_plantio") or {}
        linhas.append({
            "Estratégia": ("Atual: " if c["atual"] else "Alternativa: ") + _nome(c["rotacao"][1]),
            "Pontuação central (pesos-base do projeto)": c.get("score"),
            "Faixa (10% a 90%)": f"{M.br(d['faixa'][0])} a {M.br(d['faixa'][1])}" if d["faixa"][0] is not None else M.LACUNA,
            "Entre as 3 primeiras": M.pct(d["p_top3"]) if d["p_top3"] is not None else "(não entra no ranking)",
            "Empate técnico": f"sim, com {len(d['empatadas'])}" if d["empatadas"] else ("não" if d["p_top3"] is not None else "-"),
            "Melhor início": j.get("melhor_inicio", M.LACUNA),
            "Cobertura de critérios": M.pct(pc / pt) if pc is not None and pt else M.LACUNA,
            "Trechos citados": len(c.get("trechos") or []),
        })
    st.dataframe(pd.DataFrame(linhas), hide_index=True)


def painel_estrategias(lid: str, cultura: str, prio: str, calc: dict):
    st.subheader("3. Três caminhos para comparar (atual + 2 alternativas)")
    st.info(AVISO)
    cens = calc["cenarios"]
    atual = [c for c in cens if c["atual"]]
    alts = [c for c in cens if not c["atual"]]
    if not atual:
        lacuna("a estratégia atual não está entre os cenários.")
    if len(cens) < 3:
        lacuna(f"só {len(cens)} estratégia(s) disponível(is) com os dados; o mínimo é 3, incluindo a atual.")
    tabela_comparativa(cens, prio)
    emp = [c for c in alts if M.bloco_ranking(c, prio).get("empate_tecnico")]
    if emp:
        st.warning("Estas alternativas estão em EMPATE TÉCNICO: os dados deste app não dizem qual é melhor, então não há "
                   "'1ª' e '2ª'. Elas aparecem apenas por uma regra declarada (maior chance de ficar entre as 3 primeiras "
                   "nos sorteios de pesos). Quem decide entre elas é o técnico local.")
    elif alts:
        st.info("Nenhum empate técnico detectado entre estas alternativas e as demais candidatas, pelo critério do motor. "
                "Isso depende dos pesos e das suposições (ver Limites dos dados); não é garantia.")
    cols = st.columns(3)
    for col, (c, rot) in zip(cols, [(x, "Atual") for x in atual] + [(x, f"Alternativa {'AB'[i]}") for i, x in enumerate(alts[:2])]):
        with col:
            coluna_estrategia(c, rot, prio)
    with st.expander("Suposições do cálculo (a validar)"):
        for t in (cens[0].get("suposicoes") or []) if cens else []:
            st.markdown(f"- {t}")
        st.markdown(f"- Prioridade escolhida: {M.PRIORIDADES[prio]['rotulo']}. {M.PRIORIDADES[prio]['regra']}")
        st.caption(f"Tempo de cálculo desta seleção: {M.br(calc['segundos'], 2)} s.")


# ------------------------------------------------------------------------------------------ 3b. rotação em 3 safras
def painel_rotacao(lid: str, cultura: str, prio: str):
    st.subheader("3b. Rotação em 3 safras (uma por ano)")
    st.caption("Compara sequências de três safras seguidas, começando pela cultura que você já planta. Nenhum número vem de memória: "
               "tudo sai da tabela de culturas, do clima do local e de regras declaradas; o que falta aparece como lacuna.")
    culturas = M.culturas_disponiveis()
    opcoes = ["-"] + list(culturas)
    rotulo = lambda k: "repetir a cultura atual" if k == "-" else culturas[k]
    c1, c2, c3, c4 = st.columns(4)
    r2 = c1.selectbox("Sua rotação atual: 2ª safra (opcional)", opcoes, format_func=rotulo, key="rot2")
    r3 = c2.selectbox("Sua rotação atual: 3ª safra (opcional)", opcoes, format_func=rotulo, key="rot3")
    tex = c3.selectbox("Textura do solo (se souber)", M.OPCOES_TEXTURA, key="textura")
    mo = c4.selectbox("Matéria orgânica (se souber)", M.OPCOES_MO, key="mo")
    zarc = st.checkbox("Usar as datas de plantio do ZARC (zoneamento oficial do MAPA; só algumas culturas têm ZARC)",
                       value=False, key="zarc")
    if (r2 == "-") != (r3 == "-"):
        st.info("Para usar a sua rotação, escolha a 2ª e a 3ª safra; senão a rotação atual será a repetição da cultura atual.")
    try:
        r = rotacao_cache(lid, cultura, prio, r2, r3, tex, mo, zarc)
    except Exception as e:  # noqa: BLE001
        lacuna(f"não foi possível montar as rotações ({e.__class__.__name__}: {e}).")
        return
    if not r["estrategias"]:
        for l in r["lacunas"]:
            lacuna(l)
        return
    if r.get("empate_tecnico_todos"):
        st.warning("As duas alternativas estão em EMPATE TÉCNICO com muitas outras sequências: os dados deste app não separam as melhores. "
                   "O que separa bem é rotação x repetir a mesma cultura. Quem escolhe entre as alternativas é o agricultor com o técnico.")
    cols = st.columns(3)
    rotulos = ["Atual" if e["papel"] == "atual" else f"Alternativa {i}" for i, e in enumerate(r["estrategias"])]
    for col, e, rot in zip(cols, r["estrategias"], rotulos):
        with col:
            st.markdown(f"**{rot}**")
            st.markdown(" → ".join(e["nomes"]))
            if e["rotacao_informada_pelo_usuario"]:
                st.caption("rotação informada por você")
            st.metric("Pontuação (mediana)", M.br(e["score_mediana"], 1), help="0 a 100; não é produtividade nem lucro")
            st.caption(f"Faixa de sensibilidade (p10 a p90): {M.br(e['faixa_score'][0], 1)} a {M.br(e['faixa_score'][1], 1)}"
                       + (f" · chance de ficar entre as 3 melhores: {M.pct(e['p_top'])}" if e["p_top"] is not None else ""))
            for i, c in enumerate(e["culturas"], start=1):
                j, ctx = c["janela"], c["no_municipio"]
                txt = f"Safra {i}: **{c['nome']}**" + (f", melhor início perto de {j['inicio']}" if j else ", sem janela calculada")
                if ctx:
                    txt += f" · {M.br(ctx['area_colhida_ha'], 0)} ha colhidos no município em {ctx['ano']} (IBGE)"
                st.markdown(txt)
            with st.expander("Critérios, lacunas e riscos"):
                for k, v in e["criterios"].items():
                    st.markdown(f"- {k}: " + ("**LACUNA**" if v["lacuna"] else f"nota {M.br(v['nota_media'], 2)}"))
                for l in e["lacunas"]:
                    st.markdown(f"- LACUNA: {l}")
                for rr in e["riscos_revisao_local"]:
                    st.markdown(f"- Risco a avaliar com técnico: {rr}")
    with st.expander("Suposições da rotação (a validar)"):
        for t in r["suposicoes"]:
            st.markdown(f"- {t}")
        if zarc:
            st.markdown("- ZARC ligado: culturas sem ZARC no município não são restringidas (ver lacunas).")
        st.caption(f"Tempo de cálculo: {M.br(r['segundos'], 1)} s. {r['n_candidatas']} sequências avaliadas.")


# ------------------------------------------------------------------------------------------ 4. cenário
def painel_cenario(lid: str, cultura: str, prio: str):
    st.subheader("4. E se a chuva ou a temperatura forem diferentes?")
    st.warning("Isto NÃO é previsão de clima. Você escolhe uma variação uniforme (todos os dias do ano) para ver o quanto o resultado "
               "é sensível. Chuva mais irregular, veranicos e início da estação não são representados.")
    c1, c2 = st.columns(2)
    chuva = c1.slider("Chuva em relação ao histórico (%)", int(M.CHUVA_FATOR_MIN * 100), int(M.CHUVA_FATOR_MAX * 100), 100, 5,
                      key="fator_chuva")
    temp = c2.slider("Temperatura: aumento (°C)", M.TEMP_DELTA_MIN, M.TEMP_DELTA_MAX, 0.0, 0.5, key="delta_t")
    cc = cenario_cache(lid, cultura, prio, chuva / 100.0, float(temp))
    if chuva == 100 and temp == 0.0:
        st.info("Mova os controles para ver como as três estratégias reagem.")
    for t in cc["avisos"]:
        st.error(t)
    linhas = []
    for x in cc["linhas"]:
        linhas.append({
            "Estratégia": ("Atual: " if x["atual"] else "Alternativa: ") + _nome(x["cultura"]),
            "Adequação (histórico)": x.get("adeq_base"), "Adequação (cenário)": x.get("adeq_cenario"),
            "Anos viáveis (histórico)": M.pct(x.get("anos_viaveis_base")) if x.get("anos_viaveis_base") is not None else M.LACUNA,
            "Anos viáveis (cenário)": M.pct(x.get("anos_viaveis_cenario")) if x.get("anos_viaveis_cenario") is not None else M.LACUNA,
            "Melhor início (histórico → cenário)": f"{x.get('inicio_base', M.LACUNA)} → {x.get('inicio_cenario', M.LACUNA)}",
            "Chuva no ciclo, mm (histórico → cenário)": f"{M.br(x.get('chuva_base'), 0)} → {M.br(x.get('chuva_cenario'), 0)}",
            "Situação (histórico → cenário)": f"{x['estado_base']} → {x['estado_cenario']}",
        })
    st.dataframe(pd.DataFrame(linhas), hide_index=True)
    if cc["mudou_alternativas"]:
        st.warning("Com este clima o motor escolheria outras alternativas: "
                   f"{', '.join(_nome(x) for x in cc['alternativas_cenario'])} (no histórico: "
                   f"{', '.join(_nome(x) for x in cc['alternativas_base'])}). Como há empate técnico entre muitas candidatas, "
                   "a troca pode ser só ruído da regra de desempate declarada.")
    st.caption("Recalculamos o motor de ciclo (temperatura e chuva dentro do ciclo da cultura, ano a ano) com o clima alterado. "
               "Não usamos o modelo preditivo de NDVI aqui: ele não supera a média histórica sem a memória do próprio NDVI, e a "
               "memória do NDVI não muda quando o clima muda, então um cenário de clima quase não o move (ver Limites dos dados).")


# ------------------------------------------------------------------------------------------ páginas
def pagina_meu_local():
    st.header("Meu local: o que o satélite diz e três caminhos para conversar com o técnico")
    st.info(AVISO)
    lid, cultura, prio = entradas()
    try:
        calc = calcular_cache(lid, cultura, prio)
    except Exception as e:  # noqa: BLE001 - a tela deve mostrar a lacuna em vez de quebrar
        lacuna(f"não foi possível calcular as estratégias ({e.__class__.__name__}: {e}).")
        return
    painel_diagnostico(lid, cultura, calc)
    painel_estrategias(lid, cultura, prio, calc)
    painel_rotacao(lid, cultura, prio)
    painel_cenario(lid, cultura, prio)


def pagina_glossario():
    st.header("Glossário")
    for termo, texto in M.GLOSSARIO:
        st.markdown(f"**{termo}.** {texto}")


def pagina_limites():
    st.header("Limites dos dados")
    st.info(AVISO)
    n = M.contagens_dados()
    st.subheader("O que o satélite e o clima conseguem ver")
    for t in L.LIMITES_FIXOS:
        st.markdown(f"- {t}")
    st.markdown(f"- São {n['pontos']} locais ({n['pontos_ce']} municípios do Ceará), mas só {n['celulas_power']} células de clima "
                "distintas: locais na mesma célula têm exatamente o mesmo clima. O NDVI é novo em cada local; a chuva não.")
    st.markdown(f"- Confiança do diagnóstico por local (heurística de cobertura de dados, não é probabilidade): "
                f"{', '.join(f'{k} = {v}' for k, v in n['confianca'].items())}.")
    st.subheader("O que a previsão de NDVI consegue (e por que ela não dá nota)")
    a = M.numeros_avaliacao_195()
    if not a["disponivel"]:
        lacuna("RESULTADO.md da avaliação com 195 pontos não encontrado.")
    else:
        if a["persistencia_confirmacao_ridge"] is not None:
            st.markdown(f"- Com 195 pontos, o ganho vem da **persistência** (o verdor da quinzena anterior): skill de "
                        f"{M.br(a['persistencia_confirmacao_ridge'], 2)} sobre a média histórica na confirmação selada de 2022-2024. "
                        "'Skill' acima de 0 = melhor que repetir a média histórica.")
        st.markdown("- O **clima sozinho** não supera a média histórica fora da amostra (linha 'base' abaixo, confirmação). O "
                    "app, por isso, **não usa previsão de NDVI para dar nota**.")
        if a["confirmacao"] is not None:
            st.markdown("**Confirmação selada 2022-2024** (rodada uma vez; skill vs. média histórica)")
            st.dataframe(a["confirmacao"], hide_index=True)
        if a["selecao"] is not None:
            st.markdown("**Seleção 2010-2021**")
            st.dataframe(a["selecao"], hide_index=True)
        for l in a["linhas"]:
            st.markdown(f"> {l}")
        st.caption(f"Citado de `{a['arquivo']}`. Poucas células de clima (59), só 3 anos de confirmação: ressalvas do próprio arquivo.")
    rel = L.ler_relatorio()
    if rel["disponivel"]:
        st.markdown("**Último relatório do modelo preditivo (relatorio_modelos.md)**")
        st.dataframe(pd.DataFrame([m["linha"] for m in rel["holdout"]]), hide_index=True)
        if rel["sem_ganho_no_holdout"]:
            st.error("No holdout de 2022-2024 o modelo preditivo NÃO supera a média histórica (climatologia): "
                     f"{', '.join(rel['sem_ganho_no_holdout'])}.")
        if rel["cobertura"]["linhas"]:
            st.markdown("**Faixa de incerteza: quanto ela realmente cobre** (meta x observado)")
            st.dataframe(pd.DataFrame(rel["cobertura"]["linhas"], columns=rel["cobertura"]["cabecalho"]), hide_index=True)
            st.caption("Se o observado é menor que a meta, a faixa promete mais do que entrega (cobertura abaixo da meta).")
    else:
        lacuna(f"relatório do modelo preditivo: {rel['motivo']}")
    st.subheader("O que o motor de estratégias não sabe")
    st.markdown(f"- Faixas de temperatura e chuva vêm do EcoCrop (genéricas por espécie, não por cultivar nem por solo). "
                f"Só {n['com_n']} de {n['culturas']} culturas têm nitrogênio e palha na tabela, e esses valores vêm de estudos pontuais; "
                f"só {n['com_demanda']} têm demanda de água do ciclo.")
    st.markdown("- A duração do ciclo é SUPOSIÇÃO (ponto médio do EcoCrop); o ciclo real depende da cultivar. Pesos e prioridades "
                "são proposta do projeto, ainda sem validação com técnico.")
    st.markdown("- Não há dado de preço, custo, mercado, pragas, doenças, solo, evapotranspiração nem zoneamento (ZARC). "
                "'Renda extra' é uma lacuna: não altera o ranking.")
    aud = M.carregar_auditoria()
    if aud:
        for prio, r in aud["por_prioridade"].items():
            st.markdown(f"- Auditoria (cultura atual = {aud['cultura_atual']}, {aud['n_pontos']} locais, prioridade "
                        f"'{M.PRIORIDADES[prio]['rotulo']}'): {r['com_empate_tecnico']} de {r['alternativas_mostradas']} alternativas "
                        f"mostradas ({M.pct(r['frac_com_empate_tecnico'])}) estão em empate técnico; mediana de "
                        f"{M.br(r['mediana_n_empatadas'], 0)} candidatas empatadas; chance de ficar entre as 3 primeiras de "
                        f"{M.pct(r['p_top3_min'])} a {M.pct(r['p_top3_max'])}.")
    else:
        lacuna("auditoria das alternativas não gerada (python -m src.app.precalculo auditoria).")
    rag = M.acerto_rag()
    st.markdown(f"- Evidência do acervo (RAG): {rag if rag else 'LACUNA (número de acerto não encontrado)'}. Muitos critérios ficam "
                "'sem evidência'; o app mostra isso em vez de inventar fonte.")
    st.markdown("- O diagnóstico descreve o passado. O app não prevê chuva, não prevê colheita e não prova que uma rotação rende mais.")


def main():
    st.set_page_config(page_title="SULCO", layout="wide")
    st.title("SULCO: da órbita ao sulco")
    pagina = st.sidebar.radio("Página", ["Meu local", "Glossário", "Limites dos dados"], key="pagina")
    st.sidebar.caption(AVISO)
    {"Meu local": pagina_meu_local, "Glossário": pagina_glossario, "Limites dos dados": pagina_limites}[pagina]()


main()
