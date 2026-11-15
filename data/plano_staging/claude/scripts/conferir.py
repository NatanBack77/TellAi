import csv, os, re, random, subprocess, sys, hashlib, unicodedata, urllib.request, collections
base = r"C:\Users\Administrator\Documents\Projects\2 - Pessoal\ai\sulco-nasa\data\plano_staging\opencode"
cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fontes_baixadas")
os.makedirs(cache, exist_ok=True)

def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"-\s*\n\s*", "", s)           # hifenizacao de quebra de linha
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return s.strip()

rows = []
for e in ("01", "08", "09", "10"):
    for r in csv.DictReader(open(os.path.join(base, f"etapa_{e}.csv"), encoding="utf-8")):
        if r["status"] == "verificado":
            rows.append(r)
random.seed(7)
amostra = random.sample(rows, 40)

def texto_paginas(url):
    local = None
    if url.startswith("file://"):
        local = os.path.join(r"C:\Users\Administrator\Documents\Projects\2 - Pessoal\ai\sulco-nasa", url[7:].replace("/", os.sep))
    h = hashlib.md5(url.encode()).hexdigest()[:10]
    pdf = os.path.join(cache, h + ".pdf")
    if local and os.path.isfile(local) and not os.path.exists(pdf):
        import shutil; shutil.copy(local, pdf)
    if not os.path.exists(pdf):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            open(pdf, "wb").write(data)
        except Exception as ex:
            return None, f"download falhou: {type(ex).__name__}"
    txt = os.path.join(cache, h + ".txt")
    if not os.path.exists(txt):
        subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", pdf, txt], capture_output=True)
    if not os.path.exists(txt):
        return None, "nao e PDF/pdftotext falhou"
    pags = open(txt, encoding="utf-8", errors="replace").read().split("\f")
    return pags, None

res = collections.Counter()
detalhe = []
cacheurl = {}
for r in amostra:
    u = r["url"]
    if u not in cacheurl:
        cacheurl[u] = texto_paginas(u)
    pags, err = cacheurl[u]
    if err:
        res["nao_conferivel: " + err] += 1
        detalhe.append(("NC", r["cultura_id"], r["atributo"], u[:70], err)); continue
    t = norm(r["trecho"])
    alvo = None
    try: alvo = int(re.findall(r"\d+", r["pagina"])[0])
    except Exception: pass
    achou_pg = [i + 1 for i, p in enumerate(pags) if t and t in norm(p)]
    if not achou_pg:
        # tenta com os 8 primeiros tokens (trecho pode ter reticencias)
        ini = " ".join(t.split()[:8])
        achou_pg = [i + 1 for i, p in enumerate(pags) if ini and ini in norm(p)]
        tipo = "inicio_do_trecho"
    else:
        tipo = "trecho_inteiro"
    if not achou_pg:
        res["TRECHO_NAO_ENCONTRADO"] += 1
        detalhe.append(("X", r["cultura_id"], r["atributo"], u[:70], r["trecho"][:80]))
    else:
        ok_pg = alvo in achou_pg or any(abs(alvo - p) <= 1 for p in achou_pg) if alvo else None
        res[f"{tipo}; pagina_{'ok' if ok_pg else 'DIFERENTE'}"] += 1
        if not ok_pg:
            detalhe.append(("PG", r["cultura_id"], r["atributo"], f"citada {alvo}, achada {achou_pg[:3]}", r["trecho"][:60]))
print(len(amostra), "linhas amostradas")
for k, v in res.most_common(): print(f"  {v:3d}  {k}")
print("--- detalhes (problemas)")
for d in detalhe: print(" ", d)
