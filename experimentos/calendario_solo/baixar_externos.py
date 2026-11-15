"""Baixa (sem login) recortes de SEMENTE e MERCADO/CUSTO para staging em data/externos/ + manifesto (fonte, URL, data, sha256, licença).
PREÇO NÃO É LUCRO; custo = média regional/modelo da CONAB, não o do agricultor. Nada daqui entra no motor.
Uso: .venv/bin/python experimentos/calendario_solo/baixar_externos.py  (SIGEF ~65 MB em streaming; CONAB ~10 MB)."""
import csv, gzip, hashlib, io, json, urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "data/externos"; SAIDA.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
CONAB = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/{}.txt"
SIGEF = "https://dados.agricultura.gov.br/dataset/c7784a6e-f0ec-4196-a1ce-1d2d4784a58e/resource/6ab20c11-73a0-4ab0-8e13-2420d48dd6f5/download/sigefcamposproducaodesementes.csv"
NE = {"CE", "PE", "BA", "PI", "RN", "PB", "AL", "SE", "MA"}
PRODUTOS_PRECO = {"FEIJAO", "MILHO", "RAIZ DE MANDIOCA", "FARINHA DE MANDIOCA", "ALGODAO EM CAROCO", "MAMONA EM BAGA", "SEMENTE DE MILHO", "SORGO", "AMENDOIM", "GIRASSOL", "GERGELIM"}
man = {}


def baixar(url):
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        b = r.read()
    h.update(b)
    return b, h.hexdigest()


def conab(nome, filtro, saida, licenca_nota):
    b, sha = baixar(CONAB.format(nome))
    linhas = list(csv.DictReader(io.StringIO(b.decode("latin-1")), delimiter=";"))
    linhas = [{k.strip(): (v or "").strip() for k, v in l.items()} for l in linhas]
    sel = [l for l in linhas if filtro(l)]
    with open(SAIDA / saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sel[0])); w.writeheader(); w.writerows(sel)
    man[saida] = {"fonte": "CONAB, Portal de Informações Agropecuárias", "url": CONAB.format(nome), "data_download": str(date.today()), "sha256_bruto": sha,
                  "linhas_brutas": len(linhas), "linhas_recorte": len(sel), "licenca": licenca_nota, "encoding_origem": "latin-1", "decimal": "vírgula no original (mantido)"}


LIC = "NÃO LIDA (download aberto sem login; confira os termos do portal da CONAB antes de redistribuir)"
conab("PrecosMensalUF", lambda l: l["uf"] == "CE" and l["produto"] in PRODUTOS_PRECO, "conab_precos_mensal_uf_ce.csv", LIC)
conab("PrecosMensalMunicipio", lambda l: l["uf"] == "CE" and l["produto"] in PRODUTOS_PRECO, "conab_precos_mensal_municipio_ce.csv", LIC)
conab("CustoProducao", lambda l: l["uf"] in NE, "conab_custos_producao_nordeste.csv", LIC)

# SIGEF (MAPA): campos de produção de sementes, CE (streaming; só CE)
h, n, ce = hashlib.sha256(), 0, []
with urllib.request.urlopen(urllib.request.Request(SIGEF, headers=UA), timeout=600) as r:
    class Tee(io.RawIOBase):
        def readable(self): return True
        def readinto(self, b):
            d = r.read(len(b)); h.update(d); b[:len(d)] = d; return len(d)
    for l in csv.DictReader(io.TextIOWrapper(io.BufferedReader(Tee(), 1 << 20), encoding="utf-8-sig", newline=""), delimiter=";"):
        n += 1
        if l["UF"] == "CE": ce.append(l)
with open(SAIDA / "sigef_campos_sementes_ce.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(ce[0])); w.writeheader(); w.writerows(ce)
man["sigef_campos_sementes_ce.csv"] = {"fonte": "MAPA, SIGEF - Campos de produção de sementes (dados.agricultura.gov.br)", "url": SIGEF, "data_download": str(date.today()),
        "sha256_bruto": h.hexdigest(), "linhas_brutas": n, "linhas_recorte": len(ce), "licenca": "Creative Commons Attribution (campo license_title do CKAN)",
        "aviso": "são campos de PRODUÇÃO DE SEMENTES (inscritos no MAPA), não plantio comercial; não representa o calendário do agricultor"}
json.dump(man, open(SAIDA / "manifesto_externos.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: (v["linhas_brutas"], v["linhas_recorte"]) for k, v in man.items()}))
