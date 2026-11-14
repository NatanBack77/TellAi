"""Matriz 'cultura anterior -> cultura seguinte' com fonte (acervo local), no lugar de proxies de família/leguminosa.

Arquivo: data/culturas/matriz_rotacao.csv (uma linha por EVIDÊNCIA; todo par ordenado das 16 culturas tem ao menos uma
linha; sem evidência = linha LACUNA). Cada evidência aponta arquivo do acervo, página e trecho copiado do PDF;
`verificar_trechos` reextrai a página com pdftotext e confere (como o RAG).

Graus: favoravel | neutro | desfavoravel | LACUNA. 'neutro' = a fonte cita a sequência como opção/prática, sem efeito
descrito, ou mede e não vê diferença. Nunca é preenchido por falta de dado: falta de dado é LACUNA.
Não há intervalo de retorno por família (nenhum documento do acervo traz tabela brasileira com fonte).

Uso: from src.culturas.matriz_rotacao import carregar, consulta
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ / "data" / "culturas" / "matriz_rotacao.csv"
TABELA = RAIZ / "data" / "culturas" / "tabela_culturas.csv"
DOCS = RAIZ / "docs_rag"

COLUNAS = ["anterior", "seguinte", "grau", "criterio", "motivo", "simetrico", "arquivo", "pagina", "trecho",
           "pagina_complemento", "trecho_complemento", "tipo_evidencia", "regiao_estudo", "ressalva", "data_verificacao"]
GRAUS = {"favoravel", "neutro", "desfavoravel", "LACUNA"}
TIPOS = {"artigo_campo_semiarido", "artigo_campo_outra_regiao", "recomendacao_tecnica", "revisao"}
# Do mais para o menos forte, só para ordenar a evidência mostrada (não vira peso numérico).
ORDEM_TIPO = ["artigo_campo_semiarido", "artigo_campo_outra_regiao", "revisao", "recomendacao_tecnica"]

# Termos que identificam cada cultura no texto da fonte (conferência de que o trecho trata dela).
ALIASES = {
    "milho": ["milho", "gramíneas"], "feijao_caupi": ["caupi"], "feijao_comum": ["feijão comum", "feijão-comum", "feijoeiro", "feijão"],
    "sorgo": ["sorgo", "gramíneas"], "milheto": ["milheto", "gramíneas"], "mandioca": ["mandioca"], "algodao": ["algodão"],
    "amendoim": ["amendoim"], "girassol": ["girassol"], "mamona": ["mamona"], "gergelim": ["gergelim"],
    "guandu": ["guandu"], "palma_forrageira": ["palma"], "crotalaria_juncea": ["crotal", "sunn hemp"],
    "feijao_de_porco": ["feijão-de-porco", "feijão de porco"], "mucuna": ["mucuna"],
}


class MatrizInvalida(ValueError):
    pass


def culturas_da_tabela(caminho: Path | str = TABELA) -> list[str]:
    ids: list[str] = []
    with open(caminho, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["cultura_id"] not in ids:
                ids.append(r["cultura_id"])
    return ids


def carregar_linhas(caminho: Path | str = CAMINHO_PADRAO) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _manifesto() -> dict[str, dict]:
    m = json.loads((DOCS / "manifesto.json").read_text(encoding="utf-8"))
    return {d["arquivo"]: d for d in m["documentos"]}


def _norm(s: str) -> str:
    return " ".join(s.replace("­", "").split())


def validar(linhas: list[dict], ids: list[str] | None = None) -> list[str]:
    """Erros estruturais (sem abrir PDFs). Lista vazia = válida."""
    ids = ids or culturas_da_tabela()
    man = _manifesto()
    erros: list[str] = []
    vistos: set[tuple[str, str]] = set()
    for i, r in enumerate(linhas, start=2):
        loc = f"linha {i} ({r.get('anterior')}->{r.get('seguinte')})"
        a, s, g = r["anterior"], r["seguinte"], r["grau"]
        if a not in ids or s not in ids:
            erros.append(f"{loc}: cultura fora da tabela")
        if g not in GRAUS:
            erros.append(f"{loc}: grau inválido '{g}'")
            continue
        vistos.add((a, s))
        if g == "LACUNA":
            if any(r[c] for c in ("arquivo", "pagina", "trecho", "tipo_evidencia", "regiao_estudo")):
                erros.append(f"{loc}: LACUNA não pode ter evidência")
            if a == s:
                erros.append(f"{loc}: LACUNA na diagonal não é registrada")
            continue
        for c in ("criterio", "motivo", "arquivo", "pagina", "trecho", "tipo_evidencia", "regiao_estudo", "data_verificacao"):
            if not r[c].strip():
                erros.append(f"{loc}: campo obrigatório vazio: {c}")
        if r["tipo_evidencia"] not in TIPOS:
            erros.append(f"{loc}: tipo_evidencia inválido '{r['tipo_evidencia']}'")
        if r["arquivo"] not in man:
            erros.append(f"{loc}: arquivo fora do manifesto do acervo: {r['arquivo']}")
        elif not (DOCS / r["arquivo"]).exists():
            erros.append(f"{loc}: PDF ausente em docs_rag/")
        if not r["pagina"].strip().isdigit():
            erros.append(f"{loc}: página não numérica")
        if r["simetrico"] not in ("sim", "nao"):
            erros.append(f"{loc}: simetrico deve ser sim|nao")
        if bool(r["pagina_complemento"]) != bool(r["trecho_complemento"]):
            erros.append(f"{loc}: página e trecho de complemento andam juntos")
        texto = _norm(r["trecho"] + " " + r["trecho_complemento"]).lower()
        for papel, c in (("anterior", a), ("seguinte", s)):
            if c in ALIASES and not any(t in texto for t in ALIASES[c]):
                erros.append(f"{loc}: trecho não menciona a cultura {papel} ({c}); termos {ALIASES[c]}")
    faltam = [(a, s) for a in ids for s in ids if a != s and (a, s) not in vistos]
    if faltam:
        erros.append(f"{len(faltam)} par(es) ausente(s), ex.: {faltam[:3]}")
    return erros


def _pagina(pdf: Path, p: int) -> str:
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(p), "-l", str(p), str(pdf), "-"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return _norm(out)


def verificar_trechos(linhas: list[dict]) -> list[str]:
    """Reextrai cada página citada com pdftotext e confere que o trecho (e o complemento) está nela. Exige pdftotext."""
    if shutil.which("pdftotext") is None:
        raise RuntimeError("pdftotext (poppler) não encontrado")
    cache: dict[tuple[str, int], str] = {}
    erros: list[str] = []
    for i, r in enumerate(linhas, start=2):
        if r["grau"] == "LACUNA":
            continue
        for pag, trecho in ((r["pagina"], r["trecho"]), (r["pagina_complemento"], r["trecho_complemento"])):
            if not trecho:
                continue
            chave = (r["arquivo"], int(pag))
            if chave not in cache:
                cache[chave] = _pagina(DOCS / r["arquivo"], int(pag))
            if _norm(trecho) not in cache[chave]:
                erros.append(f"linha {i} ({r['anterior']}->{r['seguinte']}): trecho não está em {r['arquivo']} p.{pag}: "
                             f"'{trecho[:70]}...'")
    return erros


def carregar(caminho: Path | str = CAMINHO_PADRAO, validar_antes: bool = True) -> dict[tuple[str, str], list[dict]]:
    """{(anterior, seguinte): [linhas de evidência]}. Lança MatrizInvalida."""
    linhas = carregar_linhas(caminho)
    if validar_antes:
        erros = validar(linhas)
        if erros:
            raise MatrizInvalida("; ".join(erros[:10]) + (f" (+{len(erros) - 10})" if len(erros) > 10 else ""))
    out: dict[tuple[str, str], list[dict]] = {}
    for r in linhas:
        out.setdefault((r["anterior"], r["seguinte"]), []).append(r)
    return out


def _evidencia(r: dict, man: dict[str, dict]) -> dict:
    d = man.get(r["arquivo"], {})
    return {"grau": r["grau"], "criterio": r["criterio"], "motivo": r["motivo"], "arquivo": r["arquivo"],
            "titulo": d.get("titulo"), "url": d.get("url"), "pagina": int(r["pagina"]), "trecho": r["trecho"],
            "pagina_complemento": int(r["pagina_complemento"]) if r["pagina_complemento"] else None,
            "trecho_complemento": r["trecho_complemento"] or None, "tipo_evidencia": r["tipo_evidencia"],
            "regiao_estudo": r["regiao_estudo"], "ordem_na_fonte": "sem ordem (vale nos dois sentidos)" if r["simetrico"] == "sim"
            else "anterior -> seguinte", "ressalva": r["ressalva"]}


def consulta(anterior: str, seguinte: str, matriz: dict | None = None) -> dict:
    """Grau consolidado, motivo e evidências do par (anterior -> seguinte), ou LACUNA.

    Regra de consolidação (nenhum peso numérico): só neutro -> neutro; neutro + um único sentido (favoravel OU
    desfavoravel) -> esse sentido; favoravel E desfavoravel juntos -> LACUNA com divergente=True (não decide por conta
    própria; as evidências vêm em `evidencias`). Sem linha de evidência -> LACUNA. `usar_na_nota` é False em LACUNA,
    para o motor NÃO premiar nem punir par sem dado.
    """
    matriz = matriz if matriz is not None else _matriz_padrao()
    linhas = matriz.get((anterior, seguinte))
    if linhas is None:
        raise KeyError(f"par fora da matriz: {anterior} -> {seguinte}")
    reais = [r for r in linhas if r["grau"] != "LACUNA"]
    if not reais:
        return {"anterior": anterior, "seguinte": seguinte, "grau": "LACUNA", "divergente": False, "usar_na_nota": False,
                "motivo": "Nenhum documento do acervo local trata este par; o app não tem base para favorecê-lo nem puni-lo.",
                "evidencias": [], "tipo_evidencia_mais_forte": None, "regioes": []}
    man = _manifesto()
    polos = {r["grau"] for r in reais} - {"neutro"}
    divergente = polos == {"favoravel", "desfavoravel"}
    grau = "LACUNA" if divergente else (next(iter(polos)) if polos else "neutro")
    evs = sorted((_evidencia(r, man) for r in reais), key=lambda e: ORDEM_TIPO.index(e["tipo_evidencia"]))
    # tipo mais forte entre as evidências que SUSTENTAM o grau mostrado (não entre as neutras, quando há sentido)
    base = [e for e in evs if e["grau"] == grau] or evs
    motivo = ("Evidências divergentes (favorável e desfavorável por critérios diferentes): " if divergente else "") + \
             " | ".join(dict.fromkeys(f"[{e['grau']}/{e['criterio']}] {e['motivo']}" for e in evs))
    return {"anterior": anterior, "seguinte": seguinte, "grau": grau, "divergente": divergente,
            "usar_na_nota": not divergente, "motivo": motivo, "evidencias": evs,
            "tipo_evidencia_mais_forte": base[0]["tipo_evidencia"],
            "regioes": list(dict.fromkeys(e["regiao_estudo"] for e in evs))}


_CACHE: dict = {}


def _matriz_padrao() -> dict:
    if "m" not in _CACHE:
        _CACHE["m"] = carregar()
    return _CACHE["m"]


def cobertura(matriz: dict | None = None) -> dict:
    """Contagem dos 240 pares ordenados (anterior != seguinte) por grau consolidado."""
    matriz = matriz if matriz is not None else _matriz_padrao()
    cont = {"favoravel": 0, "neutro": 0, "desfavoravel": 0, "LACUNA_sem_dado": 0, "LACUNA_divergente": 0}
    for (a, s) in matriz:
        if a == s:
            continue
        c = consulta(a, s, matriz)
        if c["grau"] == "LACUNA":
            cont["LACUNA_divergente" if c["divergente"] else "LACUNA_sem_dado"] += 1
        else:
            cont[c["grau"]] += 1
    cont["pares"] = sum(cont.values())
    cont["com_evidencia"] = cont["pares"] - cont["LACUNA_sem_dado"]
    return cont


def main() -> int:
    linhas = carregar_linhas()
    erros = validar(linhas)
    if not erros and shutil.which("pdftotext"):
        erros = verificar_trechos(linhas)
    if erros:
        print(f"INVALIDA: {len(erros)} erro(s)")
        for e in erros:
            print(" -", e)
        return 1
    print("OK", cobertura(carregar(validar_antes=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
