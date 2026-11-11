import json, unicodedata, sys
import yaml
sys.path.insert(0, '.')
from src.coleta.power import celula_power
S = sys.argv[1]
cfg = yaml.safe_load(open('config.yaml', encoding='utf-8'))
mun = {str(m['id']): m['nome'] for m in json.load(open(S + '/mun.json', encoding='utf-8'))}
g = json.load(open(S + '/malha.json', encoding='utf-8'))
def ring_c(r):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        k = x0 * y1 - x1 * y0
        a += k; cx += (x0 + x1) * k; cy += (y0 + y1) * k
    return a / 2, cx / (6 * (a / 2)), cy / (6 * (a / 2))
def cent(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    A = X = Y = 0
    for p in polys:
        a, cx, cy = ring_c(p[0]); h = [ring_c(r) for r in p[1:]]
        for ha, hx, hy in h: a += -abs(ha) * (1 if a > 0 else -1) * 0 ; 
        A += abs(a); X += abs(a) * cx; Y += abs(a) * cy
    return X / A, Y / A
feats = g['features']; print(len(feats), len(mun), file=sys.stderr)
def sa(s): return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().replace(' ', '_').replace("'", '').replace('-', '_')
rows = []
for f in feats:
    cod = str(f['properties'].get('codarea') or f['properties'].get('codarea'))
    lon, lat = cent(f['geometry'])
    rows.append((mun[cod], round(lat, 4), round(lon, 4)))
usadas = {celula_power(p['lat'], p['lon'], cfg) for p in cfg['coleta']['pontos']}
best = {}
for n, lat, lon in rows:
    c = celula_power(lat, lon, cfg)
    if c in usadas: continue
    k, j = map(int, c.split('_'))
    d = ((lat - k * .5) / .5) ** 2 + ((lon - j * .625) / .625) ** 2
    if c not in best or d < best[c][0]: best[c] = (d, n, lat, lon)
out = sorted((sa(n) + '_ce', lat, lon, c) for c, (d, n, lat, lon) in best.items())
print(len(rows), 'municipios;', len(usadas), 'celulas existentes;', len(out), 'novos', file=sys.stderr)
json.dump(out, open(S + '/novos.json', 'w'))
for i, la, lo, c in out: print(f"    - {{ponto_id: {i}, lat: {la}, lon: {lo}}}")
