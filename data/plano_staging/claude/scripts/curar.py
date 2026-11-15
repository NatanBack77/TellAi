"""Biblioteca de curadoria: uma linha so entra no CSV se o trecho existir LITERALMENTE
(ignorando acentos, caixa, pontuacao e quebras de linha) na pagina citada do arquivo."""
import csv, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(HERE, "txt")
OUT = r"C:\Users\Administrator\Documents\Projects\2 - Pessoal\ai\sulco-nasa\data\plano_staging\claude"
COLS = ["cultura_id", "etapa", "atributo", "valor", "unidade", "status", "fonte", "url", "pagina",
        "trecho", "contexto", "data_consulta"]
DATA = "2026-11-15"
_cache = {}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"-\s*\n\s*(?=[a-z])", "", s)   # junta so hifenizacao de palavra (letra minuscula depois); intervalos numericos como 14-\n16 ficam
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def paginas(arq):
    if arq in _cache:
        return _cache[arq]
    out = []
    for suf in (".txt", ".raw.txt"):
        p = os.path.join(TXT, arq + suf)
        if os.path.exists(p):
            out.append([norm(x) for x in open(p, encoding="utf-8", errors="replace").read().split("\f")])
    _cache[arq] = out
    return out


class Curadoria:
    def __init__(self, etapa):
        self.etapa = etapa
        self.rows = []
        self.falhas = []

    def add(self, cultura, atributo, valor, unidade, arq, fonte, url, pagina, trecho, contexto=""):
        pgs = paginas(arq)
        t = norm(trecho)
        ok = False
        for versao in pgs:
            if 1 <= pagina <= len(versao) and t in versao[pagina - 1]:
                ok = True
        if not ok:
            achou = [i + 1 for v in pgs for i, p in enumerate(v) if t in p]
            self.falhas.append((cultura, atributo, pagina, achou[:3], trecho[:70]))
            return False
        self.rows.append(dict(cultura_id=cultura, etapa=self.etapa, atributo=atributo, valor=valor,
                              unidade=unidade, status="verificado", fonte=fonte, url=url, pagina=pagina,
                              trecho=trecho, contexto=contexto, data_consulta=DATA))
        return True

    def lacuna(self, cultura, atributo, motivo):
        self.rows.append(dict(cultura_id=cultura, etapa=self.etapa, atributo=atributo, valor="", unidade="",
                              status="lacuna", fonte="", url="", pagina="", trecho="", contexto=motivo,
                              data_consulta=DATA))

    def gravar(self):
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, f"etapa_{self.etapa:02d}.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(self.rows)
        ver = sum(r["status"] == "verificado" for r in self.rows)
        print(f"etapa {self.etapa}: {ver} verificadas, {len(self.rows) - ver} lacunas, {len(self.falhas)} REJEITADAS -> {p}")
        for f_ in self.falhas:
            print("  REJEITADA:", f_)
