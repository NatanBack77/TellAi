import sys, re, glob, os
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "txt")
pat = re.compile(sys.argv[1], re.I)
arqs = sys.argv[2].split(",")
larg = int(sys.argv[3]) if len(sys.argv) > 3 else 170
for a in arqs:
    p = os.path.join(T, a + ".txt")
    pags = open(p, encoding="utf-8", errors="replace").read().split("\f")
    for i, pg in enumerate(pags, 1):
        flat = re.sub(r"\s+", " ", pg)
        for m in pat.finditer(flat):
            s = max(0, m.start() - larg // 2); e = min(len(flat), m.end() + larg)
            print(f"[{a} p.{i}] ...{flat[s:e]}...")
