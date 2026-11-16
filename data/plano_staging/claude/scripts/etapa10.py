"""Corrige a etapa 10 (pos-colheita) do OpenCode. Nao altera o original: grava claude/etapa_10.csv."""
import csv, json, os
import curar
from curar import norm, paginas, COLS, DATA

ORIG = r"C:\Users\Administrator\Documents\Projects\2 - Pessoal\ai\sulco-nasa\data\plano_staging\opencode\etapa_10.csv"
OUT = os.path.join(curar.OUT, "etapa_10.csv")
import hashlib
UM = json.load(open(os.path.join(curar.HERE, "urlmap.json")))
REV = "REVISÃO TÉCNICA: "


def regiao(fonte):
    f = fonte
    if "Rondônia" in f: return "Embrapa Rondônia (Amazônia; não é semiárido)"
    if "Feijoeiro" in f or "Tabuleiros Costeiros" in f: return "Embrapa Tabuleiros Costeiros, publicação para a região Nordeste (2012–2014)"
    if "Meio-Norte" in f: return "Embrapa Meio-Norte (Piauí e Maranhão; não é o Ceará)"
    if "CNPSo" in f: return "Embrapa Soja (fonte nacional)"
    if "Milho e Sorgo" in f: return "Embrapa Milho e Sorgo (fonte nacional)"
    if "Semi-Árid" in f or "Semiárid" in f: return "semiárido do Nordeste"
    if "Algodão" in f: return "Embrapa Algodão (Nordeste)"
    return ""


# (cultura, atributo, prefixo do valor original) -> campos novos
E = {
 ("milho", "secagem_umidade_alvo", "13"): dict(valor="13", unidade="%", ctx="máximo para armazenar a granel"),
 ("milho", "secagem_alternativa", "colher"): dict(atributo="umidade_de_colheita_sem_secagem", valor="12 a 14", unidade="%", ctx="quando não há secagem"),
 ("milho", "monitoramento_armazem", "Monitorar"): dict(valor="Monitorar a infestação por insetos; infestação vinda do campo exige tratamento curativo, que deve ser orientado por técnico",
                                                       ctx=REV + "a fonte cita expurgo (fumigação com produto); a tela não deve orientar o procedimento"),
 ("sorgo", "secagem_umidade_alvo", "12 a 13"): dict(atributo="umidade_para_colheita_sem_secagem", valor="12 a 13", unidade="%"),
 ("feijao_caupi", "secagem_umidade_alvo", "Secagem ao sol"): dict(atributo="secagem_metodo"),
 ("feijao_caupi", "secagem_umidade_alvo", "14 a 16"): dict(atributo="umidade_que_permite_aeracao_no_lugar_de_secagem", valor="14 a 16", unidade="%",
                                                         ctx="pode-se usar aeração em silos ventilados em vez de secagem"),
 ("feijao_caupi", "armazenamento_umidade_segura", "13"): dict(atributo="umidade_referencia_comercializacao", valor="13 a 15", unidade="%",
                                                             ctx="a fonte diz U = 13% a 15%, dependendo do interesse; é referência de peso na venda, não limite de armazenamento seguro"),
 ("feijao_caupi", "manejo_preventivo", "Produtos caseiros"): dict(ctx=REV + "prática popular citada pela fonte, não validada; técnico deve avaliar antes de exibir"),
 ("feijao_caupi", "manejo_preventivo", "Evitar entrada"): dict(valor="Qualquer forma de armazenamento que evite a entrada de ar favorece a conservação dos grãos (ex.: tambores e garrafas plásticas cheios)",
                                                               trecho="Toda forma de armazenamento que evite a entrada de ar favorece a conservação dos grãos"),
 ("feijao_comum", "secagem_umidade_alvo", "13"): dict(valor="13", unidade="%", ctx="para beneficiamento e armazenamento"),
 ("feijao_comum", "secagem_temperatura_maxima", "38"): dict(valor="38", unidade="°C", ctx="em secadores"),
 ("feijao_comum", "beneficiamento", "Pré-limpeza"): dict(valor="Pré-limpeza para remover pedras, terra, torrões e restos vegetais (primeira fase do beneficiamento)"),
 ("feijao_comum", "armazenamento_umidade_segura", "15"): dict(valor="15", unidade="%", ctx="armazenamento de curto período, de até 20 dias",
                                                             trecho="Quando o armazenamento destina-se a curtos períodos, não superior a 20 dias, o teor de umidade de 15% garante a boa qualidade do produto"),
 ("feijao_comum", "manejo_preventivo", "Pilhas"): dict(valor="Pilhas de sacos dispostas de forma a permitir a maior circulação possível de ar entre elas",
                                                      ctx=REV + "a fonte também cita expurgo (fumigação), que a tela não deve orientar"),
 ("milheto", "secagem_umidade_alvo", "Abaixo"): dict(valor="15", unidade="%", ctx="máximo para sementes; acima disso ficam sujeitas a danos excessivos (beneficiamento de sementes)"),
 ("gergelim", "secagem_umidade_alvo", "Secagem dos feixes"): dict(atributo="secagem_metodo"),
 ("gergelim", "armazenamento_umidade_segura", "Local"): dict(atributo="armazenamento_condicoes"),
 ("amendoim", "secagem_umidade_alvo", "A secagem"): dict(atributo="secagem_metodo"),
 ("amendoim", "armazenamento_umidade_segura", "Amendoim"): dict(atributo="armazenamento_modo",
                                                                trecho="o amendoim em vagem geralmente é armazenado a granel em galpões ou silos"),
 ("amendoim", "contaminante_critico", "Separar"): dict(trecho="a correta separação e identificação de lotes que estejam com teores de aflatoxina acima dos permitidos pela legislação nacional"),
 ("mamona", "secagem_umidade_alvo", "Terreiro"): dict(atributo="secagem_local"),
 ("mamona", "secagem_umidade_alvo", "Cerca de 10"): dict(atributo="umidade_para_descascar", valor="10", unidade="%", ctx="para as sementes largarem da casca"),
 ("algodao", "armazenamento_umidade_segura", "8 a 10"): dict(valor="8 a 10", unidade="%", ctx="algodão em caroço"),
 ("mandioca", "armazenamento_umidade_segura", "Raízes"): dict(atributo="ramas_de_plantio_guardar", valor="Ramas guardadas perto da área de plantio, em local fresco, com umidade moderada e sombreado",
                                                              ctx="trata de guardar ramas (material de plantio), não da raiz colhida"),
}
COBERTURA = {"crotalaria_juncea", "mucuna", "feijao_de_porco"}
CULTURAS = ["milho", "feijao_caupi", "feijao_comum", "sorgo", "milheto", "girassol", "gergelim", "amendoim", "mamona", "algodao", "mandioca",
            "palma_forrageira", "guandu", "crotalaria_juncea", "mucuna", "feijao_de_porco"]

rows = list(csv.DictReader(open(ORIG, encoding="utf-8")))
out, rejeit, usadas = [], [], set()


def arq_de(url):
    return UM.get(url)


def confere(arq, pag, trecho):
    t = norm(trecho)
    return any(1 <= pag <= len(v) and t in v[pag - 1] for v in paginas(arq))


for r in rows:
    new = dict(r)
    if r["status"] == "lacuna":
        if r["cultura_id"] in COBERTURA and r["atributo"] == "armazenamento_umidade_segura":
            new["status"] = "nao_se_aplica"
            new["contexto"] = "cultura de cobertura: não há grão colhido nesta finalidade; o pós-colheita aqui seria o manejo da biomassa (não coletado)"
        out.append(new); continue
    key = next(((c, a, p) for (c, a, p) in E if c == r["cultura_id"] and a == r["atributo"] and r["valor"].startswith(p)), None)
    ctx0 = r["contexto"].strip()
    extra = ""
    if key:
        usadas.add(key); e = E[key]
        for k in ("atributo", "valor", "unidade", "trecho"):
            if k in e: new[k] = e[k]
        extra = e.get("ctx", "")
    else:
        # unidade com texto solto: mover para o contexto
        if r["unidade"] not in ("", "%", "°C"):
            extra = r["unidade"].lstrip("% ").strip(); new["unidade"] = "%" if r["unidade"].startswith("%") else ""
    reg = regiao(r["fonte"])
    new["contexto"] = "; ".join(x for x in (ctx0, extra, reg) if x)
    arq = arq_de(r["url"])
    pag = int(r["pagina"])
    if not arq or not confere(arq, pag, new["trecho"]):
        rejeit.append((r["cultura_id"], r["atributo"], pag, new["trecho"][:70])); continue
    out.append(new)

nao_usadas = [k for k in E if k not in usadas]

# linhas novas (cada uma verificada)
def nova(cultura, atributo, valor, unidade, fonte, url, arq, pag, trecho, ctx):
    if not confere(arq, pag, trecho):
        rejeit.append((cultura, atributo, pag, trecho[:70])); return
    out.append(dict(cultura_id=cultura, etapa=10, atributo=atributo, valor=valor, unidade=unidade, status="verificado", fonte=fonte, url=url,
                    pagina=pag, trecho=trecho, contexto=ctx, data_consulta=DATA))

FEI = "Embrapa Tabuleiros Costeiros. Informações Técnicas para o Cultivo do Feijoeiro (doc. 181)"
U_FEI = "http://www.cpatc.embrapa.br/publicacoes_2013/doc_181.pdf"
nova("feijao_comum", "armazenamento_umidade_segura", "12", "%", FEI, U_FEI, arq_de(U_FEI), 79,
     "Caso haja necessidade de estocagem mais prolongada, recomenda-se reduzir a umidade para 12%", "estocagem prolongada; " + regiao(FEI))
nova("feijao_comum", "armazenamento_umidade_segura", "menos de 10", "%", FEI, U_FEI, arq_de(U_FEI), 79,
     "Se os grãos forem armazenados em sacos plásticos ou recipientes vedados, a umidade deve ser inferior a 10%", "sacos plásticos ou recipientes vedados; " + regiao(FEI))
MAN = "Embrapa Mandioca e Fruticultura. Sistema de Produção de Mandioca no Semiárido"
U_MAN = "file://data/plano_staging/material_antigravity/mandioca_semiarido.pdf"
nova("mandioca", "conservacao_das_raizes_no_campo", "manter as raízes no solo até a colheita; quanto maior a idade da planta, pior a qualidade de cozimento", "", MAN, U_MAN,
     "mandioca_semiarido", 35, "para a conservação das raízes de mandioca é mantê-las no solo até a colheita", "semiárido; a fonte alerta para a perda de qualidade com a idade")
nova("mandioca", "conservacao_pos_colheita", "aplicação de parafina nas raízes, uma das técnicas pós-colheita eficientes", "", MAN, U_MAN, "mandioca_semiarido", 35,
     "Um dos métodos pós-colheita eficientes para a conservação de mandioca é a aplicação de parafina nas raízes", "semiárido; " + REV + "exige raízes colhidas há menos de 24 h, lavadas e sanificadas")

for c in CULTURAS:
    out.append(dict(cultura_id=c, etapa=10, atributo="comercializacao_preco", valor="", unidade="", status="lacuna", fonte="", url="", pagina="", trecho="",
                    contexto="sem série de preço estruturada para o produtor (CONAB só 2025–2026 e poucas culturas; ver docs/31)", data_consulta=DATA))

os.makedirs(curar.OUT, exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out)
st = {}
for o in out: st[o["status"]] = st.get(o["status"], 0) + 1
print("saída:", len(out), "linhas", st, "->", OUT)
print("REJEITADAS:", rejeit)
print("correções não aplicadas (chave não casou):", nao_usadas)
