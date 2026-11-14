"""App SULCO (Streamlit). Iniciar: .venv/bin/streamlit run src/app/app.py

Só lê arquivos locais (data/processed/...). Não chama API de dados. Chat 'Pergunte ao Sulco' usa IA só com chave (DEEPSEEK_API_KEY); sem ela, texto padrão.
Nenhum número vem do texto da tela: tudo vem de arquivo ou de código rodado; o que falta aparece como LACUNA.
Como usar e roteiro de demo: docs/11_MVP.md.
"""
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.llm.ambiente import carregar_env  # noqa: E402

carregar_env()  # .env da raiz: só SULCO_*, DEEPSEEK_*, API_*, APP_* (nunca EARTHDATA_*); não sobrescreve o ambiente
from src.app import camadas as C  # noqa: E402
from src.app import filtros as F  # noqa: E402
from src.app import logica as L  # noqa: E402
from src.app import mapa_vista as MV  # noqa: E402
from src.app import mvp as M  # noqa: E402
from src.app import quadra as Q  # noqa: E402

try:  # seções de outros módulos: se o arquivo faltar, a seção some sem quebrar o app
    from src.app import secao_balanco_renda as SBR  # noqa: E402
except ImportError:
    SBR = None
try:
    from src.app import secao_risco_solo as SRS  # noqa: E402
except ImportError:
    SRS = None

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


@st.cache_resource(show_spinner="Montando o plano de várias safras (MILP)...", max_entries=32)
def plano_cache(ponto: str, cultura: str, prioridade: str, horizonte: int, sem_repetir: bool, min_leg: int, zarc: bool) -> dict:
    return M.calcular_plano(ponto, cultura, prioridade, horizonte, sem_repetir, min_leg, zarc)


@st.cache_resource(show_spinner=False, max_entries=64)
def risco_cache(ponto: str) -> dict:
    return SRS.secao_risco_solo(ponto)


@st.cache_resource(show_spinner=False, max_entries=64)
def extremos_cache(ponto: str) -> dict:
    return SRS.secao_extremos(ponto)


@st.cache_resource(show_spinner=False, max_entries=64)
def balanco_cache(ponto: str) -> dict:
    import pandas as _pd
    clima = _pd.read_parquet(M.dir_dados() / "clima_diario.parquet", filters=[("ponto_id", "==", ponto)])    # só o ponto (leitura rápida)
    return SBR.secao_balanco_hidrico(ponto, clima)


@st.cache_resource(show_spinner=False, max_entries=64)
def renda_cache(ibge: int | None, ids: tuple) -> dict:
    return SBR.secao_renda(ibge, list(ids))


@st.cache_resource(show_spinner="Reunindo os dados do seu local para o chat...", max_entries=32)
def folha_cache(ponto: str, cultura: str, prioridade: str) -> dict:
    """Folha de fatos do local (src/llm/fatos.py): as mesmas funções da tela e da API, sem número novo."""
    from src.llm import fatos as FT
    return FT.montar_folha(ponto, cultura, prioridade, calc=calcular_cache(ponto, cultura, prioridade))


@st.cache_resource(show_spinner=False, max_entries=128)
def cenario_cache(ponto: str, cultura: str, prioridade: str, fator_chuva: float, delta_t: float) -> dict:
    return M.cenario_clima(ponto, cultura, prioridade, fator_chuva, delta_t, base=calcular_cache(ponto, cultura, prioridade))


# ------------------------------------------------------------------------------------------ 1. entrada
def _controles_camada() -> tuple[str | None, int | None]:
    """Seletor de camada e de ano do mapa. Camada sem dado (ex.: erosão sem módulo) aparece rotulada, sem quebrar."""
    c1, c2 = st.columns([2, 3])
    nomes = {k: v["rotulo"] + ("" if k != "erosao" or C.erosao_disponivel() else " (ainda sem dado)") for k, v in C.CAMADAS.items()}
    opcoes = [None] + list(C.CAMADAS)
    camada = c1.selectbox("Colorir os pontos por", opcoes, format_func=lambda k: "Só a localização (sem cor)" if k is None else nomes[k],
                          key="camada")
    ano = None
    if camada is not None and C.CAMADAS[camada]["tem_ano"]:
        anos = C.anos_disponiveis()
        escolha = c2.select_slider("Ano (linha do tempo)", ["todos os anos"] + anos, value="todos os anos", key="ano_mapa")
        ano = None if escolha == "todos os anos" else int(escolha)
    elif camada is not None:
        c2.caption("Esta camada não muda de ano para ano; o controle de ano não se aplica.")
    return camada, ano


def _legenda(camada: str, ano: int | None, v: dict, info: dict):
    if not v["disponivel"]:
        lacuna(f"camada '{C.CAMADAS[camada]['rotulo']}' sem dado: {v['nota']}. Os pontos ficam cinza.")
        return
    rampa = ", ".join(f"rgb({r},{g},{b})" for r, g, b in C.RAMPA)
    un = f" {v['unidade']}" if v["unidade"] and v["unidade"] != "cv" else ""
    st.markdown(f"<div style='display:flex;align-items:center;gap:8px;font-size:0.85rem'>menor ({M.br(info['min'], 1)}{un})"
                f"<div style='flex:0 0 160px;height:12px;border-radius:3px;background:linear-gradient(90deg,{rampa})'></div>"
                f"maior ({M.br(info['max'], 1)}{un}) · cinza = sem dado ({info['n_sem_dado']} pontos)</div>", unsafe_allow_html=True)
    st.caption(v["nota"] + " A cor usa a faixa entre os percentis 5 e 95 dos pontos, para um valor extremo não apagar o resto.")


def mapa_e_local() -> str:
    pts = M.carregar_pontos()
    ids = list(pts["ponto_id"])
    if "local" not in st.session_state or st.session_state["local"] not in ids:
        st.session_state["local"] = LOCAL_PADRAO if LOCAL_PADRAO in ids else ids[0]
    atual = st.session_state["local"]
    st.info(AVISO_KM)
    camada, ano = _controles_camada()
    o1, o2 = st.columns(2)
    aproximar = o1.checkbox("Aproximar do município escolhido (animação do mapa)", value=MV.abertura_padrao(), key="mapa_zoom",
                            help="Só visual: o mapa se aproxima do município escolhido. Não muda nenhum número.")
    sem_internet = o2.checkbox("Estou sem internet (fundo liso)", value=False, key="mapa_offline",
                               help="O fundo do mapa vem da internet. Sem ela, os pontos continuam aparecendo; este botão põe um fundo liso para dar contraste.")
    df = pts[["ponto_id", "nome", "lat", "lon"]].copy()
    if camada is None:
        df["cor"] = [[40, 110, 160, 150] for _ in ids]
        df["texto"] = df["nome"]
        v = info = None
    else:
        v = C.valores(camada, ano)
        df["cor"], info = C.cores(v["serie"], ids)
        un = f" {v['unidade']}" if v["unidade"] and v["unidade"] != "cv" else ""
        df["texto"] = [f"{n}: " + (M.br(v["serie"].get(i), 1) + un if pd.notna(v["serie"].get(i)) else "sem dado")
                       for i, n in zip(df["ponto_id"], df["nome"])]
    df["linha"] = [[220, 30, 30, 255] if i == atual else [0, 0, 0, 0] for i in df["ponto_id"]]
    df["raio"] = [11 if i == atual else 6 for i in df["ponto_id"]]
    camada_mapa = pdk.Layer("ScatterplotLayer", data=df, id="pontos", get_position="[lon, lat]", get_fill_color="cor",
                            get_line_color="linha", stroked=True, line_width_min_pixels=3, get_radius="raio", radius_units="pixels",
                            pickable=True)
    camadas_mapa = ([MV.camada_fundo_liso()] if sem_internet else []) + [camada_mapa]
    deck = pdk.Deck(layers=camadas_mapa, initial_view_state=MV.vista(pts, atual, aproximar), tooltip={"text": "{texto}"})
    ev = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="mapa", height=380,
                         alt="Mapa com os 195 locais, coloridos pela camada escolhida; clique em um ponto para escolhê-lo")
    if camada is not None:
        _legenda(camada, ano, v, info)
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
    st.caption("Clique num ponto do mapa ou use a lista abaixo. SEM INTERNET o mapa fica sem fundo (só os pontos aparecem; marque \"Estou sem internet\" para um fundo liso): o resto do "
               "app funciona igual. O ponto escolhido tem contorno vermelho.")
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
    entradas_agricultor()
    return lid, cultura, prio


def entradas_agricultor():
    """A6: manejo, água, equipamento e mercado. São FILTROS sobre as alternativas: não mudam nota nem ranking."""
    with st.expander("Condições da sua área (opcional): filtros sobre as alternativas", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.radio("Como você planta", list(F.MANEJOS), format_func=lambda k: F.MANEJOS[k], key="manejo")
        irrigado = st.session_state.get("manejo") == "irrigado"
        c2.number_input("Água de irrigação que você consegue aplicar por ciclo (mm; 0 = só a chuva)", 0, 3000, 0, 50, key="agua_irrig",
                        disabled=not irrigado, help="Só vale no manejo irrigado. 1 mm = 1 litro por metro quadrado.")
        c3.selectbox("Equipamento que você tem", F.EQUIPAMENTOS, key="equip")
        c4.selectbox("Preferência de mercado", F.MERCADOS, key="mercado")
        st.caption("Os filtros só MARCAM cada alternativa como 'atende', 'não atende' ou LACUNA, com dado de arquivo. Não mudam a pontuação, "
                   "não apagam alternativas e não dizem que uma rende mais. Equipamento e mercado não têm dado de preço nem de máquina: "
                   "viram lacuna e vão para a conversa com o técnico local.")


def filtros_atuais() -> "F.Filtros":
    ss = st.session_state
    irr = ss.get("manejo", "sequeiro") == "irrigado"
    return F.Filtros(manejo=ss.get("manejo", "sequeiro"), agua_irrigacao_mm=float(ss.get("agua_irrig", 0) or 0) if irr else 0.0,
                     equipamento=ss.get("equip", F.EQUIPAMENTOS[0]), mercado=ss.get("mercado", F.MERCADOS[0]))


def _demanda_mm(cid: str) -> float | None:
    d = (M.carregar_tabela().get(cid) or {}).get("atributos", {}).get("demanda_hidrica_mm_ciclo")
    return None if not d else d.get("valor")


_ICONE = {"atende": "atende", "nao_atende": "NÃO atende", "lacuna": "LACUNA"}


def painel_filtros(lid: str, cens: list[dict]):
    f = filtros_atuais()
    if not f.ativos():
        return
    st.markdown("#### Seus filtros sobre os três caminhos")
    if f.manejo == "irrigado":
        st.warning("LACUNA: o cálculo dos três caminhos (pontuação, faixa e janelas) segue com a chuva e o ZARC de sequeiro. O efeito da "
                   "irrigação sobre a nota não é modelado. O filtro abaixo só consulta o ZARC irrigado e compara água; confirme com o técnico local.")
    linhas, detalhes = [], []
    for c in cens:
        cid = c["rotacao"][1]
        j = c.get("janela_plantio") or {}
        res = F.avaliar(f, lid, cid, j.get("chuva_ciclo_mm"), _demanda_mm(cid))
        nome = ("Atual: " if c["atual"] else "Alternativa: ") + _nome(cid)
        linhas.append({"Estratégia": nome, "Resultado dos filtros": F.resumo(res)})
        detalhes.append((nome, res))
    st.dataframe(pd.DataFrame(linhas), hide_index=True)
    with st.expander("Detalhe de cada filtro"):
        for nome, res in detalhes:
            st.markdown(f"**{nome}**")
            for i in res["itens"]:
                st.markdown(f"- {i['filtro']} ({_ICONE[i['status']]}): {i['texto']}")
    st.caption("Alternativa que 'não atende' continua na lista (os filtros não apagam nem reordenam). A decisão é sua, com o técnico local.")


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
    painel_filtros(lid, cens)
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


# ------------------------------------------------------------------------------------------ 2b. chuva da quadra e rendimento
def painel_quadra(lid: str):
    st.subheader("2b. A chuva da quadra (fev–mai) e o rendimento das lavouras")
    ind = Q.indicador_quadra(lid)
    if "lacuna" in ind:
        lacuna(ind["lacuna"])
        return
    st.markdown(
        f"Neste local, a chuva de fevereiro a maio ({ind['anos'][0]}–{ind['anos'][1]}) teve média de **{M.br(ind['media_mm'], 0)} mm** e variou "
        f"muito de um ano para outro (desvio de {M.br(ind['desvio_mm'], 0)} mm). Em **{ind['n_secos']} de {ind['n_anos']} anos** a quadra ficou abaixo "
        f"de 80% da média (< {M.br(ind['limiar_seco_mm'], 0)} mm). A pior foi em {ind['pior_ano']} ({M.br(ind['pior_mm'], 0)} mm) e a melhor em "
        f"{ind['melhor_ano']} ({M.br(ind['melhor_mm'], 0)} mm).")
    s = ind["serie"].assign(ano=lambda d: d["ano"].astype(str))
    st.altair_chart(alt.Chart(s).mark_bar(color="#3b7ea1").encode(
        x=alt.X("ano:O", title=None), y=alt.Y("fma_mm:Q", title="Chuva de fev–mai (mm)"),
        tooltip=[alt.Tooltip("ano:O"), alt.Tooltip("fma_mm:Q", format=".0f")]).properties(height=180), width="stretch")
    ef = Q.efeito_rendimento()
    if ef:
        st.markdown("**O que isso significou para o rendimento nos dados do IBGE (municípios do Ceará, 2015–2023)**")
        linhas = [{"Cultura": k.capitalize(), "Rendimento em quadra seca (<80% da média)": f"{M.br(v['rend_ano_seco_pct'], 0)}%",
                   "Rendimento em quadra úmida (>120%)": f"+{M.br(v['rend_ano_umido_pct'], 0)}%", "Quanto a chuva explica (R²)": M.br(v["r2"], 2),
                   "Observações": v["n_obs"]} for k, v in ef.items()]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.caption("Variação do rendimento em relação à média do próprio município. É associação histórica, não causa nem previsão. O rendimento do IBGE "
                   "é estimado por agentes (não medido por parcela). Para comparação: o NDVI explica menos da produtividade (R² de 0,03 a 0,10), por isso "
                   "este app usa a chuva da quadra, e não o NDVI, como indicador de risco para a lavoura.")
    else:
        lacuna("dados do IBGE (PAM) ausentes: relação entre chuva e rendimento não mostrada.")
    st.info("Esta seção olha o PASSADO. A previsão da próxima quadra chuvosa é feita pela FUNCEME (previsão sazonal oficial do Ceará); consulte-a "
            "antes de decidir. Os índices do Pacífico e do Atlântico testados aqui não anteciparam a chuva com 24 anos de dados.")


# ------------------------------------------------------------------------------------------ 3b. rotação em 3 safras
def _nota_textura(est: dict) -> str:
    """Declara a divergência entre o rótulo de textura do motor/ZARC e a classe do SiBCS usada na seção de risco de solo."""
    try:
        from src.culturas.risco_solo import classe_textura
        sib = classe_textura(est["argila_pct"], est["areia_pct"])
    except ImportError:
        sib = None
    return (f"Atenção ao rótulo: aqui 'arenoso, médio, argiloso' é um agrupamento simples do app (argila abaixo de 15%, de 15 a 35%, acima de 35%) "
            f"usado para escolher o tipo de solo do ZARC; a fonte desses cortes NÃO foi verificada no acervo. Pelo critério do SiBCS da seção 5, "
            f"este ponto seria '{sib or M.LACUNA}'. Os dois rótulos podem diferir; confirme com o técnico local.")


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
    est = M.solo_estimado(lid)
    if est:
        st.caption(f"Solo estimado pelo mapa SoilGrids para este local (camadas 0–30 cm): argila {M.br(est['argila_pct'], 0)}%, areia {M.br(est['areia_pct'], 0)}%, "
                   f"carbono orgânico {M.br(est['carbono_organico_g_kg'], 0)} g/kg, pH {M.br(est['ph_agua'], 1)} (textura {est['textura']}). "
                   "Se você não informar a textura, esta estimativa é usada. " + est["aviso"] + " " + _nota_textura(est))
        if est.get("aviso_pixels"):
            st.warning(est["aviso_pixels"])
    else:
        lacuna("solo estimado indisponível para este local; informe a textura se souber.")
    zarc = st.checkbox("Usar as datas de plantio do ZARC (zoneamento oficial do MAPA, risco 30; só no Ceará; culturas sem ZARC usam uma janela aproximada)",
                       value=M.ZARC_PADRAO, key="zarc")
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
    fil = filtros_atuais()
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
            if fil.ativos():
                for c in e["culturas"]:
                    st.caption(f"Filtros para {c['nome']}: {F.resumo(F.avaliar(fil, lid, c['cultura'], com_agua=False))}"
                               + (" (água: só na seção 3)" if fil.manejo == "irrigado" else ""))
            with st.expander("Critérios, lacunas e riscos"):
                for k, v in e["criterios"].items():
                    st.markdown(f"- {k}: " + ("**LACUNA**" if v["lacuna"] else f"nota {M.br(v['nota_media'], 2)}"))
                for l in e["lacunas"]:
                    st.markdown(f"- LACUNA: {l}")
                for rr in e["riscos_revisao_local"]:
                    st.markdown(f"- Risco a avaliar com técnico: {rr}")
    with st.expander("Plano de várias safras com regras (programação linear inteira mista, MILP)"):
        st.caption("Para horizontes longos. Você escolhe as regras; o app resolve o melhor plano muitas vezes, sorteando pesos, ano de clima e lacunas, e conta com que "
                   "frequência cada sequência sai como a melhor. É uma PROPOSTA para conversar com o técnico: se nenhuma sequência domina, não há vencedora clara.")
        h1, h2, h3 = st.columns(3)
        hor = h1.slider("Quantas safras (uma por ano)", 3, 8, 5, key="plano_h")
        semrep = h2.checkbox("Nunca repetir a mesma cultura em seguida", value=True, key="plano_semrep")
        minleg = h3.slider("Mínimo de safras com leguminosa", 0, 3, 1, key="plano_leg")
        if st.button("Calcular o plano", key="plano_btn"):
            st.session_state["plano_pedido"] = (lid, cultura, prio, hor, semrep, minleg, zarc)
        ped = st.session_state.get("plano_pedido")
        if ped and ped[:3] == (lid, cultura, prio):
            pl = plano_cache(*ped)
            if pl.get("lacuna"):
                lacuna(pl["lacuna"])
            else:
                st.markdown(f"**{pl['n_sequencias_distintas']} sequências diferentes** saíram como a melhor em {pl['n_resolvidos']} sorteios. "
                            f"A mais frequente foi a melhor em **{M.pct(pl['p_otima_top1'])}** deles: nenhuma domina.")
                for x in pl["top"][:3]:
                    st.markdown(f"- {M.pct(x['p_otima'])} dos sorteios: " + " → ".join(x["nomes"]))
                st.caption(pl["aviso"] + f" Regras: {pl['regras']}. Tempo: {M.br(pl['segundos'], 1)} s.")
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


# ------------------------------------------------------------------------------------------ 5. solo, extremos, balanço, renda
def _avisos_e_lacunas(d: dict):
    for t in d.get("lacunas") or []:
        lacuna(t)
    for t in d.get("avisos") or []:
        st.caption(t)


def painel_risco_solo(lid: str):
    st.subheader("5. Risco de erosão e escoamento (indicador)")
    if SRS is None:
        lacuna("módulo de risco de solo não encontrado.")
        return
    d = risco_cache(lid)
    if not d["disponivel"]:
        lacuna("risco não classificado: falta pelo menos um componente (ver abaixo).")
    st.markdown(f"Classe do indicador neste local: **{d['classe']}** (soma de notas {d['soma_notas']} de {d['soma_maxima']}). "
                f"Cortes da soma: médio a partir de {d['limiares']['cortes_da_soma']['medio_a_partir_de']}, alto a partir de "
                f"{d['limiares']['cortes_da_soma']['alto_a_partir_de']} (SUPOSIÇÃO do projeto).")
    linhas = []
    for e in d["entradas"]:
        v = e["valor"]
        if isinstance(v, dict):
            v = ", ".join(f"{k.replace('_pct', '')} {M.br(x, 0)}%" for k, x in v.items() if x is not None)
        elif isinstance(v, (int, float)):
            v = M.br(v, 1)
        corte = e.get("corte")
        linhas.append({"Componente": e["componente"], "Valor de entrada": f"{v} {e.get('unidade') or ''}".strip() if v is not None else M.LACUNA,
                       "Classe": e.get("classe") or "-", "Nota": str(e["nota"]) if e["nota"] is not None else "LACUNA",
                       "Corte usado": (f"tercis entre os {corte['n_pontos']} pontos: {M.br(corte['c1'], 1)} e {M.br(corte['c2'], 1)}"
                                       if corte else (e.get("regra") or "faixa da fonte")),
                       "Fonte da faixa": e.get("fonte_faixa") or "relativo entre os pontos do projeto"})
    st.dataframe(pd.DataFrame(linhas), hide_index=True)
    st.warning("Os cortes de carbono orgânico e de dias de chuva erosiva são RELATIVOS entre os 195 pontos do projeto (tercis): 'alto' quer dizer "
               "'alto em comparação com os outros pontos', não risco absoluto. As notas são suposição do projeto, ainda sem validação com técnico.")
    with st.expander("Fontes das faixas"):
        for f in d["fontes"]:
            st.markdown(f"- {f['o_que']}: {f['fonte']} ({f['url']})")
    _avisos_e_lacunas({"lacunas": d["lacunas"], "avisos": d["avisos"]})


def painel_extremos(lid: str):
    st.subheader("5b. Calor e chuva extrema, ano a ano")
    if SRS is None:
        lacuna("módulo de extremos não encontrado.")
        return
    d = extremos_cache(lid)
    if not d["disponivel"]:
        lacuna("sem série diária de clima para este local; extremos não calculados.")
        _avisos_e_lacunas(d)
        return
    df = d["tabela_por_ano"]
    df = df.assign(ano=df["ano"].astype(str))
    c1, c2 = st.columns(2)
    for col, y, tit, cor in ((c1, "dias_quentes", "Dias quentes por ano", "#c0392b"), (c2, "dias_chuva_extrema", "Dias de chuva extrema por ano", "#2471a3")):
        col.altair_chart(alt.Chart(df, title=tit).mark_bar(color=cor).encode(
            x=alt.X("ano:O", title=None), y=alt.Y(f"{y}:Q", title="dias"), tooltip=["ano", alt.Tooltip(f"{y}:Q")]).properties(height=170),
            width="stretch")
    df_ = d["definicoes"]
    st.caption(f"Dia quente: {df_['calor']} (limiar entre {M.br(df_['limiar_tmax_c_min'], 1)} e {M.br(df_['limiar_tmax_c_max'], 1)} °C ao longo do ano). "
               f"Chuva extrema: {df_['chuva_extrema']} (limiar {M.br(df_['limiar_chuva_extrema_mm'], 1)} mm/dia). Período-base: {df_['periodo_base']}. "
               f"Fonte da definição: {df_['fonte_definicao']}.")
    nomes = {"dias_quentes": "Dias quentes", "dias_chuva_extrema": "Dias de chuva extrema", "rx1day_mm": "Maior chuva em 1 dia (mm)"}
    lin = []
    for k, t in d["tendencias"].items():
        if t.get("resultado") == "calculada":
            lin.append({"Índice": nomes.get(k, k), "Anos": str(t["n_anos"]), "Mudança por ano": M.br(t["inclinacao_por_ano"], 2),
                        "Intervalo de 95%": f"{M.br(t['ic95'][0], 2)} a {M.br(t['ic95'][1], 2)}",
                        "Tendência clara?": "não" if t["mann_kendall"] == "no trend" else "sim", "p": M.br(t["p_valor"], 2)})
        else:
            lin.append({"Índice": nomes.get(k, k), "Anos": str(t.get("n_anos", M.LACUNA)), "Mudança por ano": M.LACUNA})
    if lin:
        st.dataframe(pd.DataFrame(lin), hide_index=True)
    st.caption("'Tendência clara? não' = o teste (Mann-Kendall) não achou mudança segura; não quer dizer que nada muda.")
    _avisos_e_lacunas({"lacunas": d["lacunas"], "avisos": d["avisos"]})


def painel_balanco(lid: str):
    st.subheader("5c. Chuva menos evapotranspiração de referência (ETo), por quinzena")
    if SBR is None:
        lacuna("módulo de balanço hídrico não encontrado.")
        return
    d = balanco_cache(lid)
    q = [x for x in d["quinzenas"] if x["saldo_mm"] is not None]
    if not q:
        lacuna("balanço não calculado para este local.")
        _avisos_e_lacunas(d)
        return
    df = pd.DataFrame(q)
    ordem = list(df["rotulo"])
    base = alt.Chart(df, title="Chuva − ETo (mm por quinzena; média 2001–2024 e faixa p10–p90 entre os anos)")
    faixa = base.mark_area(opacity=0.25, color="#7f8c8d").encode(x=alt.X("rotulo:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=-60)),
                                                                 y=alt.Y("saldo_p10:Q", title="mm"), y2="saldo_p90:Q")
    linha = base.mark_line(point=True, color="#1f618d").encode(x=alt.X("rotulo:N", sort=ordem), y="saldo_mm:Q",
                                                                  tooltip=["rotulo", "chuva_mm", "eto_mm", "saldo_mm", "saldo_p10", "saldo_p90", "n_anos"])
    zero = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color="#444", strokeDash=[4, 3]).encode(y="z:Q")
    st.altair_chart((faixa + linha + zero).properties(height=240), width="stretch")
    st.info(d["aviso"])
    st.caption(f"{d.get('definicao_quinzena', '')}. Fonte: {d['fonte']['nome'] if isinstance(d['fonte'], dict) else d['fonte']}. Abaixo da linha tracejada, "
               "a atmosfera 'pede' mais água do que a chuva da quinzena traz (para uma superfície de referência, não para a sua lavoura).")
    for t in d["lacunas"]:
        lacuna(t)
    conf = d.get("conferencia_radiacao")
    if conf and conf.get("disponivel") is not False:
        with st.expander("Conferência da radiação (sanidade, não entra no cálculo)"):
            st.json({k: v for k, v in conf.items()})


def painel_renda(lid: str, cultura: str):
    st.subheader("5d. Receita bruta por hectare no município (IBGE)")
    if SBR is None:
        lacuna("módulo de renda não encontrado.")
        return
    ibge = M.carregar_pontos().set_index("ponto_id").loc[lid].get("ibge")
    ibge = None if pd.isna(ibge) else int(ibge)
    d = renda_cache(ibge, tuple(M.culturas_disponiveis()))
    st.info(d["aviso"])
    linhas = [{"Cultura": _nome(i["cultura"]), "Receita bruta (R$/ha)": M.br(i["receita_bruta_r_ha"], 0) if not i["lacuna"] else M.LACUNA,
               "Anos usados": ", ".join(str(a) for a in i["anos_usados"]) or "-", "Produto no IBGE": i["produto_pam"] or "sem correspondência",
               "Motivo da lacuna / nota": i["motivo_lacuna"] or i["nota"] or ""} for i in d["itens"]]
    st.dataframe(pd.DataFrame(linhas), hide_index=True)
    st.caption(f"{d['titulo']}. Receita bruta NÃO é lucro (sem custo nem mercado) e não é previsão. O IBGE estima o valor por agentes, "
               "e o mesmo número vale para feijão-caupi e feijão comum. Na rotação de 3 safras (3b), a prioridade 'renda extra' usa estes valores; "
               "cultura sem valor vira lacuna. A avaliar com técnico local.")


def painel_forragem():
    if SBR is None:
        return
    d = SBR.secao_forragem()
    with st.expander("Valor forrageiro (palma, sorgo, milheto): LACUNA declarada"):
        lacuna(d["aviso"])
        for i in d["itens"]:
            st.markdown(f"- **{i['cultura']}**: {i['motivo']}.")
            for x in i.get("lido", [])[:2]:
                st.caption(f"Lido em {x['arquivo']}, p. {x['pagina']}: \"{str(x['trecho'])[:250]}\" ({x['observacao']})")


# ------------------------------------------------------------------------------------------ páginas
def pagina_meu_local():
    st.header("Meu local: o que o satélite diz e três caminhos para conversar com o técnico")
    st.info(AVISO)
    lid, cultura, prio = entradas()
    st.session_state["_cenario_atual"] = (lid, cultura, prio)   # os widgets somem do estado em outras páginas; o chat lê esta cópia
    try:
        calc = calcular_cache(lid, cultura, prio)
    except Exception as e:  # noqa: BLE001 - a tela deve mostrar a lacuna em vez de quebrar
        lacuna(f"não foi possível calcular as estratégias ({e.__class__.__name__}: {e}).")
        return
    painel_diagnostico(lid, cultura, calc)
    painel_quadra(lid)
    painel_estrategias(lid, cultura, prio, calc)
    painel_rotacao(lid, cultura, prio)
    painel_cenario(lid, cultura, prio)
    for nome, f in (("risco de solo", lambda: painel_risco_solo(lid)), ("extremos", lambda: painel_extremos(lid)),
                    ("balanço hídrico", lambda: painel_balanco(lid)), ("renda", lambda: painel_renda(lid, cultura)), ("forragem", painel_forragem),
                    ("cartão do município", lambda: painel_cartao(lid, cultura, prio, calc))):
        try:
            f()
        except Exception as e:  # noqa: BLE001 - uma seção com defeito vira lacuna, não derruba o app
            lacuna(f"seção '{nome}' não pôde ser montada ({e.__class__.__name__}: {e}).")
    secoes_opcionais(lid, cultura, prio)


def painel_cartao(lid: str, cultura: str, prio: str, calc: dict):
    """AP1: cartão de uma folha do município, com os mesmos dados da tela (sem número novo)."""
    from src.app import cartao as CT
    st.subheader("6. Cartão do município (uma folha, para levar ao técnico)")
    ss = st.session_state
    rot = rotacao_cache(lid, cultura, prio, ss.get("rot2", "-"), ss.get("rot3", "-"), ss.get("textura", "não sei"), ss.get("mo", "não sei"),
                        bool(ss.get("zarc", M.ZARC_PADRAO)))
    c = CT.montar_cartao(lid, cultura, prio, calc=calc, rotacao=rot)
    c1, c2 = st.columns(2)
    nome_arq = f"cartao_sulco_{lid}"
    c1.download_button("Baixar cartão (HTML, para imprimir)", CT.cartao_html(c).encode("utf-8"), file_name=nome_arq + ".html",
                       mime="text/html", key="cartao_html")
    pdf = CT.cartao_pdf(c)
    if pdf is not None:
        c2.download_button("Baixar cartão (PDF)", pdf, file_name=nome_arq + ".pdf", mime="application/pdf", key="cartao_pdf")
    else:
        c2.caption("PDF indisponível (biblioteca fpdf2 não instalada); use o HTML e imprima pelo navegador.")
    st.caption(CT.AVISO_FINAL + " O cartão repete o que está nesta tela: nenhum número novo.")


def secoes_opcionais(lid: str, cultura: str, prio: str):
    """Seções de outros módulos: qualquer função `secao_*` de src/app/secao_*.py. Módulo ausente = a seção some; erro = LACUNA, sem quebrar.

    Contrato: `secao_xxx(ponto_id, cultura, prioridade)` desenha com `streamlit` (aceita menos argumentos posicionais, na mesma ordem) e
    traz o atributo `secao_xxx.desenha_streamlit = True`. Sem o atributo a função é ignorada (as que só devolvem dict esperam a integração).
    """
    pacote = [str(Path(__file__).parent)]
    for info in sorted(pkgutil.iter_modules(pacote), key=lambda m: m.name):
        if not info.name.startswith("secao_"):
            continue
        try:
            mod = importlib.import_module(f"src.app.{info.name}")
        except ImportError:
            continue
        except Exception as e:  # noqa: BLE001 - módulo com defeito não derruba o app
            lacuna(f"seção '{info.name}' não carregou ({e.__class__.__name__}: {e}).")
            continue
        for nome, fn in sorted(vars(mod).items()):
            if not (nome.startswith("secao_") and callable(fn) and getattr(fn, "desenha_streamlit", False)):
                continue            # funções `secao_*` que só devolvem dados (dict) não são chamadas aqui: a integração final as desenha
            n = len(inspect.signature(fn).parameters)
            try:
                fn(*(lid, cultura, prio)[:n])
            except Exception as e:  # noqa: BLE001
                lacuna(f"seção '{nome}' falhou ({e.__class__.__name__}: {e}).")


def pagina_glossario():
    st.header("Glossário")
    st.caption("Explicações curtas, em linguagem simples. Onde há trecho do acervo, ele foi copiado do PDF indicado (página do arquivo PDF). "
               "Confira o PDF e converse com o técnico local.")
    for termo, texto, trecho in M.glossario_atual():
        st.markdown(f"**{termo}.** {texto}")
        if trecho:
            st.caption(f"Do acervo ({trecho['arquivo']}, p. {trecho['pagina']}): \"{trecho['trecho']}\"")


def pagina_limites():
    st.header("Limites dos dados")
    st.info(AVISO)
    lin = M.limites_linhas()
    st.subheader("O que o satélite e o clima conseguem ver")
    for t in lin["visao_geral"]:
        st.markdown(f"- {t}")
    st.subheader("O que a previsão de NDVI consegue (e por que ela não dá nota)")
    a = M.numeros_avaliacao_195()
    if not a["disponivel"]:
        lacuna("RESULTADO.md da avaliação com 195 pontos não encontrado.")
    else:
        for t in lin["previsao"]:
            st.markdown(f"- {t}")
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
        st.markdown("**Último relatório do modelo preditivo** (`data/processed/modelos/relatorio_modelos.md`)")
        st.dataframe(pd.DataFrame([m["linha"] for m in rel["holdout"]]), hide_index=True)
        try:
            if "persistência **ligada**" in L.caminho_relatorio().read_text(encoding="utf-8"):
                st.caption("Este relatório usa a persistência (o verdor da quinzena anterior) como variável: o ganho sobre a média histórica "
                           "vem dela, não do clima sozinho (ver a seção acima).")
        except OSError:
            pass
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
    for t in lin["motor"]:
        (lacuna if t.startswith("LACUNA") else st.markdown)(t if t.startswith("LACUNA") else f"- {t}")


EXEMPLOS_CHAT = ["Como vai ficar a vegetação nas próximas semanas?",
                 "Por que o Sulco sugeriu esses caminhos?",
                 "O que é empate técnico?",
                 "Quantos milímetros de chuva o feijão-caupi precisa durante o ciclo?"]
ROTULO_ORIGEM_CHAT = {"llm": "Gerado por IA a partir dos fatos do seu local e dos trechos do acervo (números e citações conferidos)",
                      "template": "Texto padrão, sem IA",
                      "sem_evidencia": "Sem evidência nos dados nem no acervo",
                      "recusa": "Pedido fora do que a ferramenta faz"}


def _folha_do_local_visto():
    """Folha de fatos do local que o usuário escolheu em 'Meu local' (sem nome, lat/lon, ponto_id nem IBGE nos textos)."""
    ref = st.session_state.get("_cenario_atual")
    return folha_cache(*ref) if ref else None


def _mostrar_resposta_chat(item: dict):
    r = item["resposta"]
    st.markdown(f"**Você perguntou:** {item['pergunta']}")
    sel = ROTULO_ORIGEM_CHAT.get(r["origem"], r["origem"])
    (st.success if r["origem"] == "llm" else st.info)(f"{sel}.")
    st.markdown(r["resposta"])
    if r["origem"] != "llm" and r.get("motivo") and r["origem"] in ("template", "sem_evidencia"):
        st.caption(f"Por quê: {r['motivo']}")
    if r["verificacao"]["ok"] is False:
        st.caption("O texto da IA foi barrado pelo verificador: " + "; ".join(r["verificacao"]["motivos"]))
    if r.get("uso"):
        st.caption(f"Tokens usados: {r['uso'].get('total_tokens')}")
    if r.get("fatos") or r["trechos"] or r.get("resposta_com_citacoes"):
        with st.expander("De onde veio esta resposta", expanded=False):
            if r.get("resposta_com_citacoes") and r["resposta_com_citacoes"] != r["resposta"]:
                st.caption("Texto com as citações (o que o verificador conferiu):")
                st.write(r["resposta_com_citacoes"])
            if r.get("fatos"):
                st.markdown("**Fatos do seu local usados** (cada um mostra a frase simples, o texto técnico e de onde veio):")
                for f in r["fatos"]:
                    marca = " (citado no texto)" if f["id"] in r.get("citados_fatos", []) else ""
                    st.markdown(f"**[{f['id']}] {f['rotulo']}{' (lacuna)' if f['lacuna'] else ''}{marca}**")
                    st.write(f.get("texto_simples") or "(sem frase simples)")
                    st.caption(f"Texto técnico: {f['texto']}  |  Origem: {f['origem']}")
            if r["trechos"]:
                st.markdown("**Trechos do acervo** (confira no PDF):")
                for t in r["trechos"]:
                    marca = " (citado no texto)" if t["n"] in r.get("citados", []) else ""
                    st.markdown(f"**[{t['n']}] {t['arquivo']}, p. {t['pagina']}{marca}**")
                    st.write(t["texto"])
    st.caption(r["aviso"])


def pagina_pergunte():
    from src.llm import chat as CH
    st.header("Pergunte ao Sulco")
    st.info("Perguntas sobre cultivo e rotação (documentos do acervo: ZARC, Embrapa, cartilhas), sobre o próprio Sulco e sobre os dados do local "
            "que você escolheu em 'Meu local' (previsão do verdor, diagnóstico, caminhos, solo, risco, ETo, receita bruta, ZARC). "
            "Aqui não se escolhe rotação, não se prevê chuva nem colheita e não se promete lucro. " + AVISO)
    est = CH.estado()
    if est["ia_ativa"]:
        st.success(f"IA ligada ({est['provedor']}, modelo {est['modelo']}). Só a pergunta e os fatos e trechos relevantes são enviados; nunca o nome do "
                   "município, as coordenadas, o código do município nem o identificador do local.")
    else:
        st.warning(f"IA desligada. {est['mensagem']} Você ainda recebe os trechos do acervo, em texto padrão, sem internet.")
    ss = st.session_state
    ss.setdefault("chat_hist", [])
    st.caption("Exemplos (clique para preencher):")
    cols = st.columns(len(EXEMPLOS_CHAT))
    for i, ex in enumerate(EXEMPLOS_CHAT):
        if cols[i].button(ex, key=f"chat_ex_{i}"):
            ss["chat_pergunta"] = ex
    tem_cen = bool(ss.get("_cenario_atual"))
    with st.form("form_chat", clear_on_submit=False):
        pergunta = st.text_input("Sua pergunta (em português simples)", key="chat_pergunta", max_chars=CH.MAX_PERGUNTA)
        usar_ctx = st.checkbox("Usar os dados do local que escolhi em 'Meu local' (previsão, diagnóstico, caminhos, solo...)",
                               value=tem_cen, disabled=not tem_cen, key="chat_usar_ctx",
                               help=None if tem_cen else "Abra a página 'Meu local' e escolha um município antes.")
        enviar = st.form_submit_button("Perguntar")
    if enviar:
        folha = None
        from src.llm import fatos as FT
        if usar_ctx and tem_cen and FT.temas_da_pergunta(pergunta or ""):   # só monta os dados do local se a pergunta é sobre eles
            try:
                folha = _folha_do_local_visto()
            except Exception as e:  # noqa: BLE001 - sem os dados do local o chat segue só com o acervo e o 'sobre o Sulco'
                lacuna(f"não foi possível reunir os dados do local para o chat ({e.__class__.__name__}).")
        with st.spinner("Buscando nos dados e no acervo..."):
            r = CH.responder_chat(pergunta, folha=folha)
        ss["chat_hist"] = ([{"pergunta": pergunta, "resposta": r}] + ss["chat_hist"])[:10]
    for item in ss["chat_hist"]:
        st.divider()
        _mostrar_resposta_chat(item)
    if not ss["chat_hist"]:
        st.caption("Ainda não há perguntas. Cada resposta é independente das anteriores (o histórico é só para você rever).")


def main():
    st.set_page_config(page_title="SULCO", layout="wide")
    st.title("SULCO: da órbita ao sulco")
    pagina = st.sidebar.radio("Página", ["Meu local", "Pergunte ao Sulco", "Glossário", "Limites dos dados"], key="pagina")
    st.sidebar.caption(AVISO)
    {"Meu local": pagina_meu_local, "Pergunte ao Sulco": pagina_pergunte, "Glossário": pagina_glossario, "Limites dos dados": pagina_limites}[pagina]()


main()
