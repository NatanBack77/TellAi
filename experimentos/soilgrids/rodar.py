"""Uso: rodar.py selecao [placebo SEMENTE] | confirma v1,v2,... (UMA vez, 2022-2024)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nucleo as N
OUT = Path(__file__).resolve().parent
if __name__ == "__main__":
    df = N.carregar_df()
    if sys.argv[1] == "selecao":
        sem = int(sys.argv[3]) if len(sys.argv) > 2 and sys.argv[2] == "placebo" else None
        vs = ["base", "v1_solo", "v2_ad", "v3_inter", "v4_solo", "v4_ref"] if sem is None else ["base", "v1_solo", "v2_ad", "v3_inter", "v4_solo"]
        r = N.rodar(df, list(range(2010, 2022)), sem, vs)
        r.to_parquet(OUT / (f"pred_selecao_placebo{sem}.pq" if sem is not None else "pred_selecao.pq"), index=False)
    else:
        fin = ["base"] + sys.argv[2].split(",")
        r = N.rodar(df, [2022, 2023, 2024], None, fin)
        r.to_parquet(OUT / "pred_confirmacao.pq", index=False)
