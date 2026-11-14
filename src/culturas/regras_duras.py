"""Regras DURAS do agricultor: o que ele não pode ou não quer plantar, o que precisa plantar e quantas safras seguidas aceita da mesma cultura/família.

Regra dura é restrição, não nota: uma sequência que a viola NÃO entra como alternativa (nem pesa no ranking). Não há dado agronômico aqui; os
valores vêm do próprio agricultor. Nenhum limite padrão é inventado: todo campo vem DESLIGADO (None / vazio), de modo que sem regras o resultado do
motor é exatamente o de antes. O que já existia no código continua valendo por fora destas regras (`rotacao.py`: alternativa não é monocultura).

Campos (todos opcionais):
  proibidas             culturas que ele NÃO pode ou NÃO quer plantar (nas safras 2 em diante; a safra 1 é a cultura atual, já plantada);
  obrigatorias          culturas que PRECISAM aparecer na sequência (a atual conta);
  exigir_alguma_de      "cobertura": ao menos UMA cultura deste grupo precisa aparecer (a lista é do agricultor/técnico; a tabela de culturas não
                        classifica cobertura, então o app não decide quais são);
  max_seguidas_cultura  máximo de safras SEGUIDAS da mesma cultura (SUPOSIÇÃO do agricultor; sem padrão agronômico);
  max_seguidas_familia  idem, para a mesma família botânica (cultura sem família na tabela não conta como repetição: lacuna, não vantagem);
  aceita_pousio         só registra a preferência. Pousio NÃO é modelado como safra (não há dado de nota para ele); aparece em `nao_modelado`.
Chaves antigas do MILP (`sem_repetir_seguida`, `min_leguminosas`, `max_repeticoes`) continuam aceitas em `verificar`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

LEGUMINOSA = "Leguminosae"


def _fs(x: Iterable[str] | None) -> frozenset[str]:
    return frozenset(x or ())


@dataclass(frozen=True)
class RegrasDuras:
    proibidas: frozenset[str] = field(default_factory=frozenset)
    obrigatorias: frozenset[str] = field(default_factory=frozenset)
    exigir_alguma_de: frozenset[str] = field(default_factory=frozenset)
    max_seguidas_cultura: int | None = None
    max_seguidas_familia: int | None = None
    aceita_pousio: bool = False

    def __post_init__(self):
        for nome in ("proibidas", "obrigatorias", "exigir_alguma_de"):
            object.__setattr__(self, nome, _fs(getattr(self, nome)))
        for nome in ("max_seguidas_cultura", "max_seguidas_familia"):
            v = getattr(self, nome)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 1):
                raise ValueError(f"{nome} deve ser inteiro >= 1 ou None")
        if self.proibidas & self.obrigatorias:
            raise ValueError("cultura não pode ser proibida e obrigatória: " + ", ".join(sorted(self.proibidas & self.obrigatorias)))
        if self.exigir_alguma_de and self.exigir_alguma_de <= self.proibidas:
            raise ValueError("todas as culturas de `exigir_alguma_de` estão proibidas")

    @property
    def vazia(self) -> bool:
        return not (self.proibidas or self.obrigatorias or self.exigir_alguma_de or self.max_seguidas_cultura or self.max_seguidas_familia)

    def para_dict(self) -> dict:
        return {"proibidas": sorted(self.proibidas), "obrigatorias": sorted(self.obrigatorias), "exigir_alguma_de": sorted(self.exigir_alguma_de),
                "max_seguidas_cultura": self.max_seguidas_cultura, "max_seguidas_familia": self.max_seguidas_familia,
                "aceita_pousio": self.aceita_pousio}

    def nao_modelado(self) -> list[str]:
        return (["pousio: preferência registrada, mas pousio não entra como safra (sem dado para dar nota a ele)"] if self.aceita_pousio else [])

    def validar_contra(self, culturas: Iterable[str]) -> None:
        """Erro se a regra cita cultura que não existe (typo não pode virar regra ignorada em silêncio)."""
        desc = (self.proibidas | self.obrigatorias | self.exigir_alguma_de) - set(culturas)
        if desc:
            raise ValueError("culturas desconhecidas nas regras: " + ", ".join(sorted(desc)))


def normalizar(regras) -> dict:
    """Aceita None, RegrasDuras ou dict (inclui as chaves antigas do MILP). Devolve dict com todas as chaves."""
    base = {"proibidas": frozenset(), "obrigatorias": frozenset(), "exigir_alguma_de": frozenset(), "max_seguidas_cultura": None,
            "max_seguidas_familia": None, "sem_repetir_seguida": False, "min_leguminosas": None, "max_repeticoes": None}
    if regras is None:
        return base
    if isinstance(regras, RegrasDuras):
        d = regras.para_dict()
    else:
        d = dict(regras)
    out = dict(base)
    out.update({k: v for k, v in d.items() if k in base})
    for k in ("proibidas", "obrigatorias", "exigir_alguma_de"):
        out[k] = _fs(out[k])
    return out


def _maior_corrida(chaves: list) -> int:
    """Maior número de safras seguidas com a mesma chave (chave None = sem informação: não conta como repetição)."""
    melhor, atual, ant = 0, 0, object()
    for k in chaves:
        if k is None:
            atual, ant = 0, object()
            continue
        atual = atual + 1 if k == ant else 1
        ant = k
        melhor = max(melhor, atual)
    return melhor


def verificar(seq: Iterable[str], familia: dict[str, str | None], regras) -> list[str]:
    """Lista de violações (vazia = sequência permitida). `seq[0]` é a cultura atual: já plantada, logo não é checada contra `proibidas`."""
    s = list(seq)
    r = normalizar(regras)
    v = []
    proib = sorted(c for c in set(s[1:]) if c in r["proibidas"])
    if proib:
        v.append("usa cultura proibida pelo agricultor: " + ", ".join(proib))
    falta = sorted(c for c in r["obrigatorias"] if c not in s)
    if falta:
        v.append("falta cultura obrigatória: " + ", ".join(falta))
    if r["exigir_alguma_de"] and not (set(s) & r["exigir_alguma_de"]):
        v.append("nenhuma cultura do grupo exigido (cobertura) aparece")
    if r["max_seguidas_cultura"] and _maior_corrida(s) > r["max_seguidas_cultura"]:
        v.append(f"mais de {r['max_seguidas_cultura']} safras seguidas da mesma cultura")
    if r["max_seguidas_familia"] and _maior_corrida([familia.get(c) for c in s]) > r["max_seguidas_familia"]:
        v.append(f"mais de {r['max_seguidas_familia']} safras seguidas da mesma família botânica")
    if r["sem_repetir_seguida"] and any(a == b for a, b in zip(s[:-1], s[1:])):
        v.append("repete a mesma cultura em safras seguidas")
    if r["min_leguminosas"] and sum(familia.get(c) == LEGUMINOSA for c in s) < r["min_leguminosas"]:
        v.append(f"menos de {r['min_leguminosas']} safras de leguminosa")
    if r["max_repeticoes"] and s and max(s.count(c) for c in set(s)) > r["max_repeticoes"]:
        v.append(f"alguma cultura aparece mais de {r['max_repeticoes']} vezes")
    return v


def permite(seq: Iterable[str], familia: dict[str, str | None], regras) -> bool:
    return not verificar(seq, familia, regras)


def separar(candidatas: list[tuple[str, ...]], familia: dict[str, str | None], regras) -> tuple[list[tuple[str, ...]], list[dict]]:
    """(permitidas, descartadas). Descartada = {'sequencia', 'motivos'}: a tela mostra 'descartadas e por quê'. Mantém a ordem de entrada."""
    ok, fora = [], []
    for s in candidatas:
        m = verificar(s, familia, regras)
        if m:
            fora.append({"sequencia": list(s), "motivos": m})
        else:
            ok.append(s)
    return ok, fora


def resumo_descartes(descartadas: list[dict]) -> dict[str, int]:
    """Quantas sequências saíram por cada motivo (uma sequência pode ter mais de um motivo)."""
    out: dict[str, int] = {}
    for d in descartadas:
        for m in d["motivos"]:
            out[m] = out.get(m, 0) + 1
    return dict(sorted(out.items()))


def descrever(regras, descartadas: list[dict] | None = None, base_viola: list[str] | None = None, max_exemplos: int = 20) -> dict:
    """Bloco para a saída/tela: regras ativas, descartadas por motivo (com alguns exemplos) e se a rotação atual as viola."""
    r = normalizar(regras)
    ativa = {k: (sorted(v) if isinstance(v, frozenset) else v) for k, v in r.items() if v}
    d = descartadas or []
    return {"regras": ativa, "n_descartadas": len(d), "descartadas_por_motivo": resumo_descartes(d), "descartadas_exemplos": d[:max_exemplos],
            "base_viola": list(base_viola or []),
            "nao_modelado": regras.nao_modelado() if isinstance(regras, RegrasDuras) else []}


def validar(regras, culturas: Iterable[str]) -> None:
    """Erro se a regra (dict ou RegrasDuras) cita cultura fora da tabela."""
    r = normalizar(regras)
    desc = (r["proibidas"] | r["obrigatorias"] | r["exigir_alguma_de"]) - set(culturas)
    if desc:
        raise ValueError("culturas desconhecidas nas regras: " + ", ".join(sorted(desc)))
