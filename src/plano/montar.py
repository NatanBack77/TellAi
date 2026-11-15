"""Monta o plano de plantio de 10 etapas para um local e uma cultura (docs/34_PLANO_DE_PLANTIO.md).

- Etapas curadas (1, 4 a 10): dado com fonte de `data/plano/plano_plantio.csv`. O que falta aparece como lacuna; cultura de cobertura sem grão, como "não se aplica".
- Etapas do motor (2 e 3): vêm de `fornecedores` (injetáveis; a rota usa `src.plano.motor_etapas`). Falha do motor = lacuna visível.
- Regras do produto aplicadas AQUI (não dependem do front): nenhum caminho de arquivo na saída; trecho que cita produto/fumigação NÃO sai; a nota interna
  de revisão técnica não sai (só o aviso `requer_tecnico`); lacuna nunca tem valor; sem promessa de colheita, lucro ou clima futuro.
"""
from __future__ import annotations

import re
from typing import Callable

from src.plano import dados
from src.plano.etapas import ETAPAS, limpar_caminhos, marcar_destaques, rotulo

VERSAO = "plano-1"
AVISO = "Apoio à decisão: converse com o técnico antes de decidir. O plano mostra o que as fontes e os dados dizem; não promete colheita, lucro nem clima futuro."
LIMITES = [
    "Os dados das etapas vêm de publicações da Embrapa, da FAO e do MAPA, muitas de outras regiões; o campo 'contexto' de cada item diz a origem.",
    "Nenhum técnico local revisou este plano.",
    "Satélite e clima não enxergam o seu talhão; o solo é estimado de um mapa global, não é análise de solo.",
    "Não há preço, custo nem mercado.",
]
Fornecedor = Callable[[str, str], dict]


def _fonte(ln: dados.Linha) -> dict | None:
    if not ln.fonte:
        return None
    return {"nome": ln.fonte, "pagina": ln.pagina, "url": ln.url if ln.url.startswith("http") else None}


def _item(ln: dados.Linha) -> dict:
    proib = dados.termo_proibido(ln.trecho) is not None
    return {"atributo": ln.atributo, "rotulo": rotulo(ln.atributo), "valor": ln.valor, "unidade": ln.unidade, "status": "verificado",
            "fonte": _fonte(ln), "trecho": None if proib else ln.trecho, "contexto": ln.contexto, "requer_tecnico": ln.requer_tecnico or proib,
            "referencia_da_fonte": ln.etapa == 7 or "referencia" in ln.atributo,
            "experimento": "experimento" in ln.atributo or "ATENÇÃO" in ln.contexto}


def _kc_txt(v: str) -> str:
    """'0.60-0.35 (nota 6)' -> '0,60 a 0,35' (vírgula decimal; a nota de rodapé da FAO não ajuda o agricultor)."""
    v = re.sub(r"\s*\(nota \d+\)", "", v)
    v = re.sub(r"(\d)\.(\d)", r"\1,\2", v)
    return re.sub(r"(\d)-(\d)", r"\1 a \2", v)


def _agrupar_kc(itens: list[dict]) -> list[dict]:
    """Kc inicial, médio e final viram UMA linha ('inicial 0,4 · médio 1,15 · final 0,35'): resposta mais objetiva, mesma fonte."""
    out = list(itens)
    for sufixo, nome in (("", "kc"), ("_ano1", "kc_ano1")):
        partes = {f: next((i for i in out if i["atributo"] == f"kc_{f}{sufixo}"), None) for f in ("inicial", "medio", "final")}
        if not all(partes.values()):
            continue
        base = partes["medio"]
        novo = {**base, "atributo": nome, "rotulo": rotulo(nome), "unidade": "",   # mantém o trecho da linha de Kc médio (a linha da tabela da FAO)
                "valor": f"inicial {_kc_txt(partes['inicial']['valor'])} · médio {_kc_txt(partes['medio']['valor'])} · final {_kc_txt(partes['final']['valor'])}",
                "requer_tecnico": any(p["requer_tecnico"] for p in partes.values())}
        pos = out.index(base)
        out = [i for i in out if i not in partes.values()]
        out.insert(min(pos, len(out)), novo)
    return out


def _etapa_curada(numero: int, ds: dict, cultura_id: str) -> dict:
    linhas = ds.get((cultura_id, numero), [])
    itens, lacunas = [], []
    for ln in linhas:
        if ln.status == "verificado":
            itens.append(_item(ln))
        elif ln.status == "lacuna":
            lacunas.append(f"{rotulo(ln.atributo)}: {ln.contexto or 'sem dado'}")
        elif ln.status == "nao_se_aplica":
            lacunas.append(f"{rotulo(ln.atributo)}: não se aplica a esta cultura ({ln.contexto})" if ln.contexto else f"{rotulo(ln.atributo)}: não se aplica a esta cultura")
    if numero == 6:
        itens = _agrupar_kc(itens)
    marcar_destaques(numero, itens)
    nao_se_aplica = bool(linhas) and not itens and all(ln.status == "nao_se_aplica" for ln in linhas)
    if nao_se_aplica:
        lacunas = [f"{rotulo(ln.atributo)}: {ln.contexto}" for ln in linhas]
    elif not itens:
        lacunas.insert(0, "Ainda não há dado com fonte para esta cultura nesta etapa.")
    return {"itens": itens, "lacunas": lacunas, "nao_se_aplica": nao_se_aplica}


def _sem_caminhos(item: dict) -> dict:
    """Rede de segurança nos itens do motor: nenhum texto sai com caminho de arquivo interno, venha de onde vier."""
    novo = dict(item)
    for k in ("valor", "contexto", "rotulo"):
        if isinstance(novo.get(k), str):
            novo[k] = limpar_caminhos(novo[k])
    if isinstance(novo.get("fonte"), dict):
        novo["fonte"] = {**novo["fonte"], "nome": limpar_caminhos(str(novo["fonte"].get("nome", "")))}
    return novo


def _etapa_motor(numero: int, forn: Fornecedor | None, ponto_id: str, cultura_id: str) -> dict:
    if forn is None:
        return {"itens": [], "lacunas": ["Esta etapa vem do cálculo do local, que não está disponível neste momento."], "nao_se_aplica": False}
    try:
        r = forn(ponto_id, cultura_id)
    except Exception:   # noqa: BLE001 - qualquer falha do motor vira lacuna; nunca preenche valor
        return {"itens": [], "lacunas": ["O cálculo do local falhou neste momento; tente de novo."], "nao_se_aplica": False}
    itens = [_sem_caminhos(i) for i in (r.get("itens") or [])]
    lacunas = [limpar_caminhos(x) for x in (r.get("lacunas") or [])]
    marcar_destaques(numero, itens)
    if not itens:
        lacunas.insert(0, "Sem resultado do cálculo do local para esta cultura.")
    return {"itens": itens, "lacunas": lacunas, "nao_se_aplica": False}


def culturas_com_plano(ds: dict | None = None) -> list[str]:
    ds = ds if ds is not None else dados.carregar()
    return sorted({c for c, _ in ds})


def montar(ponto_id: str, cultura_id: str, nome_cultura: str | None = None, fornecedores: dict[int, Fornecedor] | None = None,
           ds: dict | None = None, exemplo: bool = False) -> dict:
    ds = ds if ds is not None else dados.carregar()
    if cultura_id not in culturas_com_plano(ds):
        raise ValueError(f"cultura '{cultura_id}' sem plano de plantio")
    fornecedores = fornecedores or {}
    etapas, cobertura = [], {}
    for numero, slug, titulo, origem in ETAPAS:
        e = _etapa_curada(numero, ds, cultura_id) if origem == "curado" else _etapa_motor(numero, fornecedores.get(numero), ponto_id, cultura_id)
        cobertura[str(numero)] = len(e["itens"])
        etapas.append({"numero": numero, "slug": slug, "titulo": titulo, "origem": "dado_curado" if origem == "curado" else "motor",
                       "itens": e["itens"], "lacunas": e["lacunas"], "nao_se_aplica": e["nao_se_aplica"], "aviso_tecnico": True})
    return {"versao": VERSAO, "ponto_id": ponto_id, "cultura": cultura_id, "cultura_nome": nome_cultura or cultura_id, "cultura_exemplo": exemplo, "etapas": etapas,
            "cobertura_itens": cobertura, "limites": LIMITES, "aviso": AVISO}
