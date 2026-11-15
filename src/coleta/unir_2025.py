"""Une os dados originais (2001-2024) com os de 2025+ em arquivos de ENTRADA DE INFERÊNCIA.

    python -m src.coleta.unir_2025            # gera/atualiza os dois arquivos *_atual.parquet (idempotente)

Saídas (config.yaml, `caminhos.clima_atual` / `caminhos.ndvi_atual`):
  data/processed/clima_diario_atual.parquet = clima_diario.parquet + clima_2025plus.parquet
  data/processed/ndvi_16d_atual.parquet     = ndvi_16d.parquet     + ndvi_2025plus.parquet

Regras (nada é inventado nem preenchido):
- Os parquets ORIGINAIS nunca são abertos para escrita. Treino, validação e métricas continuam lendo os originais;
  os arquivos "atuais" servem só para a previsão do próximo composto (`src/modelos/previsao.py`).
- Mesmo schema e mesmos tipos do original; ordenado por (ponto_id, data); NaN continua NaN (os últimos dias do POWER vêm vazios
  e assim ficam: quem calcula janela decide se há cobertura; ver `features.py`).
- NDVI: todas as linhas e valores de `confiabilidade` são mantidos como vieram (0, 1, 3, NaN). O filtro "aceita 0 e 1" é
  `ndvi.confiabilidade_aceita` do config, aplicado depois, em `diagnostico.preparar_ndvi`.
- De-duplicação DECLARADA: se a mesma (ponto_id, data) aparece mais de uma vez (dentro de uma fonte ou entre as duas), fica a
  PRIMEIRA ocorrência na ordem [original, 2025plus]; o relatório conta quantas linhas saíram e quantas tinham valores DIFERENTES.
  (Em 2026-11-14 não havia nenhuma: as duas fontes não se sobrepõem.)
- `celula_power` de um ponto tem de ser igual nas duas fontes; senão, erro (não se mistura célula de clima em silêncio).
- Idempotente: sempre refeito a partir dos originais; o arquivo só é regravado se o conteúdo mudou.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config

CHAVE = ["ponto_id", "data"]


def unir(orig: pd.DataFrame, novo: pd.DataFrame, nome: str) -> tuple[pd.DataFrame, dict]:
    """União pura (sem disco). Devolve (tabela, relatório)."""
    falta = [c for c in orig.columns if c not in novo.columns]
    extra = [c for c in novo.columns if c not in orig.columns]
    if falta or extra:
        raise DadosInvalidos(f"'{nome}': colunas diferentes entre original e 2025plus (faltam {falta}, a mais {extra}).")
    novo = novo[list(orig.columns)].astype(orig.dtypes.to_dict())
    if "celula_power" in orig.columns:
        a = orig.groupby("ponto_id")["celula_power"].agg(lambda s: s.iloc[0])
        b = novo.groupby("ponto_id")["celula_power"].agg(lambda s: s.iloc[0])
        comuns = a.index.intersection(b.index)
        dif = [p for p in comuns if a[p] != b[p]]
        if dif:
            raise DadosInvalidos(f"'{nome}': celula_power difere entre original e 2025plus em {dif[:5]}: não unir.")
    tudo = pd.concat([orig.assign(_fonte=0), novo.assign(_fonte=1)], ignore_index=True)
    valores = [c for c in orig.columns if c not in CHAVE]
    dup = tudo.duplicated(CHAVE, keep=False)
    conflitos = 0
    if dup.any():
        g = tudo[dup].groupby(CHAVE)[valores]
        conflitos = int((g.nunique(dropna=False) > 1).any(axis=1).sum())   # grupos com valores diferentes
    saida = tudo.drop_duplicates(CHAVE, keep="first").sort_values(CHAVE, kind="stable")
    saida = saida.drop(columns="_fonte").reset_index(drop=True)
    rel = {"arquivo": nome, "linhas_original": int(len(orig)), "linhas_2025plus": int(len(novo)), "linhas_saida": int(len(saida)),
           "duplicadas_removidas": int(len(tudo) - len(saida)), "grupos_duplicados_com_valores_diferentes": conflitos,
           "data_min": str(saida["data"].min().date()), "data_max": str(saida["data"].max().date()),
           "pontos": int(saida["ponto_id"].nunique())}
    return saida, rel


def _gravar_se_mudou(df: pd.DataFrame, destino: Path) -> bool:
    if destino.is_file():
        try:
            if pd.read_parquet(destino).equals(df):
                os.utime(destino)   # conteúdo igual: só marca como atualizado (o cache e o `garantir_atuais` comparam mtime)
                return False
        except Exception:   # arquivo corrompido: regrava
            pass
    tmp = destino.with_suffix(".tmp.parquet")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, destino)
    return True


def unir_tudo(cfg: dict | None = None, base: Path | None = None) -> dict:
    """Gera os dois arquivos *_atual. Devolve o relatório (também vai para `unir_2025_relatorio.json`)."""
    cfg = cfg or carregar_config()
    base = Path(base) if base else RAIZ
    cam = cfg["caminhos"]
    rel = {}
    for tipo, orig_k, novo_k, atual_k in (("clima", "clima", "clima_2025plus", "clima_atual"),
                                           ("ndvi", "ndvi", "ndvi_2025plus", "ndvi_atual")):
        o, n = base / cam[orig_k], base / cam[novo_k]
        for arq in (o, n):
            if not arq.is_file():
                raise DadosInvalidos(f"Arquivo ausente para a união de {tipo}: {arq}")
        orig, novo = pd.read_parquet(o), pd.read_parquet(n)
        for d in (orig, novo):
            d["data"] = pd.to_datetime(d["data"])
        saida, r = unir(orig, novo, Path(cam[atual_k]).name)
        r["regravado"] = _gravar_se_mudou(saida, base / cam[atual_k])
        if tipo == "clima":
            ok = saida.dropna(subset=["chuva_mm", "tmax_c"])
            r["ultimo_dia_com_chuva_e_tmax"] = str(ok["data"].max().date())
            r["linhas_com_chuva_nan"] = int(saida["chuva_mm"].isna().sum())
            r["nota"] = ("os últimos dias do POWER vêm vazios (NaN, mantidos); os mais recentes podem ser provisórios "
                         "(hipótese, não verificada).")
        else:
            r["confiabilidade_contagem"] = {("NaN" if pd.isna(k) else str(int(k))): int(v)
                                            for k, v in saida["confiabilidade"].value_counts(dropna=False).items()}
            r["confiabilidade_aceita_config"] = cfg["ndvi"]["confiabilidade_aceita"]
        rel[tipo] = r
    (base / cam["clima_atual"]).parent.joinpath("unir_2025_relatorio.json").write_text(
        json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    return rel


def garantir_atuais(cfg: dict, base: Path | None = None) -> None:
    """Gera os arquivos *_atual se faltarem ou estiverem mais velhos que alguma fonte (só leitura de arquivos locais)."""
    base = Path(base) if base else RAIZ
    cam = cfg["caminhos"]
    fontes = [base / cam[k] for k in ("clima", "ndvi", "clima_2025plus", "ndvi_2025plus")]
    atuais = [base / cam["clima_atual"], base / cam["ndvi_atual"]]
    if all(a.is_file() for a in atuais) and all(a.stat().st_mtime >= max(f.stat().st_mtime for f in fontes) for a in atuais):
        return
    unir_tudo(cfg, base)


if __name__ == "__main__":
    print(json.dumps(unir_tudo(), ensure_ascii=False, indent=2))
    sys.exit(0)
