"""Verificador deterministico da saida do LLM (sem LLM). Falhou => o servico descarta e usa o template."""
from __future__ import annotations

import json
import re
import unicodedata

AVISO = "a avaliar com tecnico local"
MAX_CHARS = 3000
PROMESSAS = [
    r"rende mais", r"render[aá] mais", r"vai render", r"rendimento (maior|garantido)",
    # 'garantia' sozinha ("não é garantia") não é promessa; só as formas afirmativas
    r"garante\w*", r"garantem", r"garantid[oa]s?", r"garantir\w*", r"garantindo", r"garantia de (lucro|rendimento|colheita|renda|produtividade|safra)",
    r"aumenta a renda",
    r"aumentar a renda", r"aumento de renda", r"lucr\w*", r"mais dinheiro", r"ganhar mais", r"retorno financeiro",
    r"aumenta a produtividade", r"aumentar a produtividade", r"dobra\w*", r"com certeza", r"certamente",
    r"sem risco", r"infal\w+", r"100 ?%", r"enriquec\w*", r"produz mais", r"colhe mais",
]
_NEGACAO = re.compile(r"\b(nao|nem|sem|nunca|jamais|nenhum\w*|ninguem|impossivel)\b")
_PROM = [re.compile(unicodedata.normalize("NFD", p).encode("ascii", "ignore").decode()) for p in PROMESSAS]
PALAVRAS_NUM = ("um uma primeiro primeira segunda terceiro terceira dois duas tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete "
                "dezoito dezenove vinte trinta quarenta cinquenta sessenta setenta oitenta noventa cem cento mil milhao "
                "milhoes metade dobro triplo").split()
_CIT = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_CIT_F = re.compile(r"\[(F\d+(?:\s*[,;]\s*F\d+)*)\]")   # citação de FATO da folha do local: [F3], [F3, F7]
_NUM = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*")


# ---- TOM para o agricultor (só no chat, `tom=True`): resposta curta e sem termo técnico sem tradução ----
MAX_PALAVRAS_CHAT = 140
TERMOS_PROIBIDOS = ["ndvi", "anomalia", "composto", "compostos", "faixa de incerteza", "intervalo", "percentil", "skill", "rmse", "r2", "r²",
                    "aci", "conformal", "monte carlo", "sorteio", "sorteios", "persistencia", "climatologia", "modis", "power", "smap",
                    "empate tecnico", "holdout", "bootstrap", "p90", "p-valor"]
_TERMOS_RE = [(t, re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")) for t in TERMOS_PROIBIDOS]
# contagens pequenas por extenso aceitas quando o item contado existe na fonte (ex.: 'três caminhos', 'duas semanas')
_CONTAGEM = re.compile(r"\b(dois|duas|tres)\s+(caminhos?|alternativas?|semanas?|culturas?|opcoes|meses|etapas)\b")
_RAIZ_ITEM = {"caminho": "caminho", "alternativa": "alternativ", "semana": "semana", "cultura": "cultura", "opcoes": "opc", "meses": "mes",
              "etapas": "etapa"}
_MARCA_CIT = re.compile(r"\[\s*F?\d+(?:\s*[,;]\s*F?\d+)*\s*\]")
_APROX = re.compile(r"(cerca de|quase|uns|umas|perto de|mais ou menos|em torno de)\s+$")


# afirmações prescritivas (ordem/recomendação): o chat só relata o que o material ou os dados dizem
PRESCRITIVAS = ["pode sim", "deve plantar", "deve cultivar", "deve escolher", "voce deve", "recomendo", "recomendamos", "plante ", "vale a pena",
                "o melhor e plantar", "sim, plante"]
_PRESC_RE = [(t.strip(), re.compile(r"(?<![a-z])" + re.escape(t))) for t in PRESCRITIVAS]
_RESTATE = re.compile(r"^(ou seja|isto e|isso e|em outras palavras|quer dizer|ou melhor)\b")
_STOP_SIM = set("para com que uma uns umas dos das nos nas por como mais mas nao sim seu sua seus suas esse essa isso este esta aos ele ela eles "
                "elas foi sao ser tem ter vai ate sobre entre quando onde qual quais".split())


def _conteudo(frase: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", sem_acento(frase.lower())) if w not in _STOP_SIM}


def frases_repetidas(texto: str) -> list[tuple[str, str]]:
    """Pares de frases CONSECUTIVAS que dizem quase a mesma coisa: palavras de conteúdo quase iguais (Jaccard >= 0,7), texto quase igual
    (SequenceMatcher >= 0,85) ou 2a frase que reformula ('ou seja...') com >= 50% das palavras da menor já na outra e >= 2 em comum."""
    import difflib
    fr = [f.strip() for f in re.split(r"(?<=[.!?])\s+", _MARCA_CIT.sub(" ", texto)) if len(f.strip()) > 3]
    out = []
    for a, b in zip(fr, fr[1:]):
        ca, cb = _conteudo(a), _conteudo(b)
        if not ca or not cb:
            continue
        inter = len(ca & cb)
        jac = inter / len(ca | cb)
        sm = difflib.SequenceMatcher(None, sem_acento(a.lower()), sem_acento(b.lower())).ratio()
        reform = bool(_RESTATE.match(sem_acento(b.lower()))) and inter >= 2 and inter / min(len(ca), len(cb)) >= 0.5
        # frases PARALELAS sobre coisas diferentes ('Milheto pede cerca de 450 mm.' / 'Milho pede cerca de 500 mm.') não são repetição:
        # o sujeito (1ª palavra de conteúdo) ou os números mudam
        suj = lambda x: (re.findall(r"[a-zà-ú-]{3,}", sem_acento(x.lower())) or [""])[0]
        nums = lambda x: re.findall(r"\d+(?:[.,]\d+)?", x)
        paralelas = (suj(a) != suj(b) or (nums(a) and nums(a) != nums(b))) and not reform
        if ((len(ca) >= 3 and len(cb) >= 3 and jac >= 0.7) or sm >= 0.85 or reform) and not paralelas:
            out.append((a, b))
    return out


def contar_palavras(texto: str) -> int:
    return len(re.findall(r"[A-Za-zÀ-ÿ0-9]+(?:[-'][A-Za-zÀ-ÿ0-9]+)*", _MARCA_CIT.sub(" ", texto)))


def termos_tecnicos(texto: str, permitidos: str = "") -> list[str]:
    """Termos proibidos (sem tradução) que aparecem no texto; os que o próprio agricultor escreveu na pergunta são permitidos."""
    n, perm = sem_acento(texto.lower()), sem_acento(permitidos.lower())
    return [t for t, r in _TERMOS_RE if r.search(n) and not r.search(perm)]


def limpar_citacoes(texto: str) -> str:
    """Texto para EXIBIR: tira [F7], [3], [1][4], [F2, F5] (depois da verificação), espaço antes de pontuação e frases que ficam vazias."""
    if not isinstance(texto, str):
        return ""
    t = _MARCA_CIT.sub("", texto)
    t = re.sub(r"[ \t]+([.,;:!?])", r"\1", t)          # ' [F2] .' -> '.'
    t = re.sub(r"([.!?])(\s*[.,;:])+", r"\1", t)        # '. .' / '.,' sobrando
    t = re.sub(r"(^|\n)[ \t]*[-•]?[ \t]*[.,;:]*[ \t]*(?=\n|$)", r"\1", t)   # linha ou item que ficou vazio
    t = re.sub(r"(^|\n)[ \t]*[.,;:]+[ \t]*", r"\1", t)   # pontuação que sobrou no começo da linha
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _variantes(tok: str) -> set[float]:
    """Interpretacoes numericas de um token com tolerancia pt-BR/en ('1.234,5', '0,35', '0.35', '1.234')."""
    out: set[float] = set()
    try:
        if "," in tok and "." in tok:
            dec = "," if tok.rfind(",") > tok.rfind(".") else "."
            mil = "." if dec == "," else ","
            out.add(float(tok.replace(mil, "").replace(dec, ".")))
        elif "," in tok or "." in tok:
            sep = "," if "," in tok else "."
            partes = tok.split(sep)
            if len(partes) > 2:
                out.add(float("".join(partes)))
            else:
                out.add(float(partes[0] + "." + partes[1]))
                if len(partes[1]) == 3 and len(partes[0]) <= 3:
                    out.add(float(partes[0] + partes[1]))
        else:
            out.add(float(tok))
    except ValueError:
        pass
    return out


def _decimais(tok: str) -> int:
    m = re.search(r"[.,](\d+)$", tok)
    return len(m.group(1)) if m and not (len(m.group(1)) == 3 and re.fullmatch(r"\d{1,3}[.,]\d{3}", tok)) else 0


def numeros_da_fonte(*fontes) -> set[float]:
    """Todos os numeros presentes em JSON/texto/trechos de origem."""
    vals: set[float] = set()

    def visita(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            vals.add(float(x))
            vals.update(_variantes(repr(x)))
        elif isinstance(x, str):
            for t in re.findall(r"\d+(?:[.,]\d+)*", x):
                vals.update(_variantes(t))
        elif isinstance(x, dict):
            for k, v in x.items():
                visita(str(k))
                visita(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                visita(v)

    for f in fontes:
        visita(f)
    return vals


def _no_conjunto(tok: str, fonte: set[float]) -> bool:
    d = _decimais(tok)
    for v in _variantes(tok):
        for s in fonte:
            if abs(s - v) <= 1e-9 * max(1.0, abs(s)):
                return True
            if d >= 1 and abs(s - v) <= 0.5 * 10 ** -d + 1e-9:
                return True
    return False


# números de dois a dez por extenso NÃO precisam de fonte, salvo quando ligados a unidade, porcentagem, R$, dias, anos, vezes etc.
SMALL_NUM = {"um", "uma", "dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
             "primeiro", "primeira", "segunda", "terceiro", "terceira"}   # ('segundo' é também preposição: não entra)
_UNIDADE = (r"(?:por cento|%|reais|real|mm|milimetros?|graus|dias?|anos?|vezes|meses|mes|semanas?|quinzenas?|decendios?|hectares?|ha|"
            r"quilos?|kg|litros?|metros?|km|toneladas?|sacas?|horas?)\b")


def _ligada_a_unidade(norm: str, m: re.Match) -> bool:
    return bool(re.match(r"\s+" + _UNIDADE, norm[m.end():]) or re.search(r"r\$\s*$", norm[:m.start()]))


def _contagem_ok(norm: str, ocorr: list, fonte_txt: str) -> bool:
    """Toda ocorrência (dois/duas/tres) é seguida de um item contável (caminhos, alternativas, semanas...) que aparece nas fontes."""
    if not ocorr:
        return False
    for m in ocorr:
        if m.group().lower() not in ("dois", "duas", "tres"):
            return False
        c = _CONTAGEM.match(norm, m.start())
        if not c:
            return False
        item = c.group(2)
        raiz = _RAIZ_ITEM.get(item[:-1] if item.endswith("s") and item[:-1] in _RAIZ_ITEM else item)
        if not raiz or raiz not in fonte_txt:
            return False
    return True


def _arredondado_de(tok: str, fonte: set[float]) -> bool:
    """'600' é arredondamento (até 5%) de algum número da fonte; só para inteiros redondos (múltiplos de 10) escritos com 'cerca de' etc."""
    try:
        v = float(tok.replace(".", "").replace(",", "."))
    except ValueError:
        return False
    return v >= 20 and v % 10 == 0 and any(s > 0 and abs(s - v) / s <= 0.05 for s in fonte)


def citacoes(texto: str) -> list[int]:
    return [int(n) for g in _CIT.findall(texto) for n in re.split(r"[,;]", g)]


def citacoes_fatos(texto: str) -> list[str]:
    """Ids de fatos citados no texto, ex.: ['F3', 'F7']."""
    return [x.strip() for g in _CIT_F.findall(texto) for x in re.split(r"[,;]", g)]


def verificar(texto, cenario_json=None, trechos=None, exigir_citacao: bool | None = None, fatos=None, tom: bool = False,
              pergunta: str = "", exigir_aviso: bool = True) -> dict:
    """Retorna {'ok': bool, 'motivos': [..]}. `trechos`: lista de {n, texto, ...} enviados ao modelo.

    `fatos` (opcional): lista de {id: 'F3', texto} da folha de fatos do local enviada ao modelo. Com fatos, [F#] é validado como [n]
    e todo número do texto tem de existir nos fatos/trechos CITADOS (ou no JSON do cenário); sem citação alguma, falha.
    Se o fato tem `texto_simples`, é ele (o que o modelo viu) a fonte dos números. `tom=True` (chat): máx. de palavras e sem termo técnico.
    `exigir_aviso=False` (chat): o fecho ('converse com o técnico') é anexado por código depois da verificação, não exigido da IA."""
    motivos: list[str] = []
    trechos = [t for t in (trechos or []) if isinstance(t, dict)]
    fatos = [f for f in (fatos or []) if isinstance(f, dict)]
    if not isinstance(texto, str) or not texto.strip():
        return {"ok": False, "motivos": ["saida vazia"]}
    if len(texto) > MAX_CHARS:
        motivos.append("saida longa demais")
    existentes = {t.get("n") for t in trechos}
    for n in sorted(set(citacoes(texto))):
        if n not in existentes:
            motivos.append(f"citacao [{n}] inexistente")
    ids_fatos = {f.get("id") for f in fatos}
    cit_f = citacoes_fatos(texto)
    for fid in sorted(set(cit_f)):
        if fid not in ids_fatos:
            motivos.append(f"citacao [{fid}] inexistente")
    if (exigir_citacao if exigir_citacao is not None else bool(trechos or fatos)) and not citacoes(texto) and not cit_f:
        motivos.append("sem citacao [n]" if not fatos else "sem citacao [F#] nem [n]")
    sem_cit = _CIT_F.sub(" ", _CIT.sub(" ", texto))
    if fatos:       # com folha de fatos: só vale número presente no que foi CITADO (fatos e trechos) ou no JSON do cenário
        usados = [t.get("texto", "") for t in trechos if t.get("n") in set(citacoes(texto))]
        usados += [f.get("texto_simples") or f.get("texto", "") for f in fatos if f.get("id") in set(cit_f)]
        fonte = numeros_da_fonte(cenario_json, usados)
    else:
        fonte = numeros_da_fonte(cenario_json, [t.get("texto", "") for t in trechos])
    for m in _NUM.finditer(sem_cit):
        tok = m.group()
        if _no_conjunto(tok, fonte):
            continue
        if _APROX.search(sem_cit[:m.start()]) and _arredondado_de(tok, fonte):
            continue                      # 'cerca de 600 mm' para 619 mm da fonte
        motivos.append(f"numero '{tok}' fora da fonte")
    norm = sem_acento(texto.lower())
    for p in _PROM:
        for m in p.finditer(norm):
            if _NEGACAO.search(norm[max(0, m.start() - 70):m.start()].rsplit(".", 1)[-1]):      # janela de 70: "não tenho dado de preço nem de custo para dizer se dá lucro"
                continue                  # 'não garante', 'sem garantia', 'não prometo': negação passa
            motivos.append(f"promessa proibida: '{m.group()}'")
            break
    fonte_txt = sem_acento(json.dumps(cenario_json, ensure_ascii=False).lower() + " " +
                           " ".join(str(t.get("texto", "")) for t in trechos).lower() + " " +
                           " ".join(str(f.get("texto_simples") or f.get("texto", "")) for f in fatos).lower())
    for w in PALAVRAS_NUM:
        ocorr = list(re.finditer(rf"\b{w}\b", norm))
        if not ocorr:
            continue
        if w in SMALL_NUM:       # um..dez e ordinais: só valem sem fonte se soltos; ligados a unidade exigem a MESMA expressão na fonte
            def sem_fonte(m, w=w):
                nxt = re.match(r"\s+(\w+)", norm[m.end():])
                return not (nxt and re.search(rf"\b{w}\s+{nxt.group(1)}\b", fonte_txt))
            ocorr = [m for m in ocorr if _ligada_a_unidade(norm, m) and not (w == "duas" and re.match(r"\s+semanas\b", norm[m.end():]))
                     and sem_fonte(m)]
        elif re.search(rf"\b{w}\b", fonte_txt):
            continue
        if not ocorr or _contagem_ok(norm, ocorr, fonte_txt):
            continue              # solto, ou contagem de item que existe nas fontes ('três caminhos', 'duas semanas')
        motivos.append(f"numero por extenso '{w}' fora da fonte")
    if exigir_aviso and AVISO not in norm and not re.search(r"convers\w+ com o tecnico", norm):
        motivos.append("falta o aviso 'a avaliar com técnico local'")
    if tom:
        n_pal = contar_palavras(texto)
        if n_pal > MAX_PALAVRAS_CHAT:
            motivos.append(f"resposta longa demais para o agricultor ({n_pal} palavras; máximo {MAX_PALAVRAS_CHAT})")
        for t in termos_tecnicos(texto, pergunta):
            motivos.append(f"termo técnico sem tradução: '{t}'")
        nt = sem_acento(texto.lower())
        for t, r in _PRESC_RE:
            if r.search(nt):
                motivos.append(f"afirmação prescritiva (ordem ou recomendação): '{t}'")
        for a, b in frases_repetidas(texto):
            motivos.append(f"frases repetidas: '{a[:40]}...' e '{b[:40]}...'")
    return {"ok": not motivos, "motivos": motivos}
