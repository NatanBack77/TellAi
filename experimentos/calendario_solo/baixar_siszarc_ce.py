"""SISZARC (MAPA): cultivares INDICADAS no ZARC por safra/cultura/UF -> data/externos/siszarc_cultivares_ce.csv (só CE). Streaming do .csv.gz (~250 MB)."""
import csv, gzip, hashlib, io, json, urllib.request
from datetime import date
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
URL = "https://dados.agricultura.gov.br/dataset/d68e269e-dbe5-44d9-83ec-1f0871427773/resource/97038867-7afc-4f93-85ef-f39cf8368581/download/siszarc_cronograma.csv.gz"
h = hashlib.sha256(); n = 0; ce = []
r = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=900)
class Tee(io.RawIOBase):
    def readable(self): return True
    def readinto(self, b):
        d = r.read(len(b)); h.update(d); b[:len(d)] = d; return len(d)
with gzip.open(io.BufferedReader(Tee(), 1 << 20), "rt", encoding="utf-8-sig", newline="") as f:
    for l in csv.DictReader(f, delimiter=";"):
        n += 1
        if l["UF"] == "CE": ce.append(l)
out = RAIZ / "data/externos/siszarc_cultivares_ce.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(ce[0])); w.writeheader(); w.writerows(ce)
m = json.load(open(RAIZ / "data/externos/manifesto_externos.json"))
m["siszarc_cultivares_ce.csv"] = {"fonte": "MAPA, SISZARC - cultivares indicadas no ZARC (dados.agricultura.gov.br; dataset marcado 'EM MANUTENÇÃO' no título em 2026-11-14)", "url": URL,
    "data_download": str(date.today()), "sha256_bruto": h.hexdigest(), "linhas_brutas": n, "linhas_recorte": len(ce), "licenca": "Creative Commons Attribution (campo license_title do CKAN)"}
json.dump(m, open(RAIZ / "data/externos/manifesto_externos.json", "w"), ensure_ascii=False, indent=1)
print(n, len(ce))
