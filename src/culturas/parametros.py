"""Parâmetros EXPLÍCITOS do motor (ciclo + incerteza). Todo padrão aqui é SUPOSIÇÃO de projeto, não fato.

Cada padrão depende de decisão do usuário e é escrito em `suposicoes` de cada cenário (ver `Parametros.suposicoes`).
Nenhum valor agronômico mora aqui: faixas de temperatura/chuva e ciclo vêm de data/culturas/tabela_culturas.csv.
"""
from __future__ import annotations

from dataclasses import dataclass

CICLO_MODOS = ("min", "medio", "max")
CHUVA_MODOS = ("ciclo", "anual")


@dataclass(frozen=True)
class Parametros:
    # --- ciclo e janela (decisão do usuário: ciclo real, data de início) ---
    passo_inicio_dias: int = 10      # grade de inícios: a cada N dias a partir de 1º/jan (10 = 36 decêndios)
    ciclo_modo: str = "medio"        # duração: 'min', 'medio' (ponto médio) ou 'max' de ciclo_min/max_dias (EcoCrop)
    chuva_modo: str = "ciclo"        # 'ciclo' = chuva acumulada no ciclo; 'anual' = 365 dias desde o início
    ciclo_override: tuple = ()       # opcional: ((cultura_id, dias), ...) substitui a duração do ciclo dessas culturas (padrão () = nada muda)
    risco_max: float = 0.30          # fração de anos que pode falhar (nota 0) para a cultura seguir 'viável'
    ano_ini: int = 2001
    ano_fim: int = 2024
    min_anos: int = 10               # mínimo de anos completos para avaliar; abaixo disso 'indeterminada'
    # --- Monte Carlo (SMAA-2) ---
    n_sorteios: int = 10000
    semente: int = 20241112
    dirichlet_alfa: float = 1.0      # 1 = uniforme no simplex (máxima ignorância sobre os pesos)
    ordem_pesos: tuple | None = None  # ordem de importância (do maior ao menor); None = sem restrição
    bloco_ranking: str = "principal"  # bloco que ESCOLHE as alternativas: 'principal' (critérios comuns) ou 'completo' (5 critérios, lacuna = U[0,1])
    percentil_baixo: float = 10.0
    percentil_alto: float = 90.0
    top_n: int = 3
    tol_empate: float = 1e-9         # diferença de score (escala 0-100) tratada como igual
    # --- ZARC (docs/13): restringe os inícios de plantio aos decêndios indicados; DESLIGADO por padrão ---
    usar_zarc: bool = False
    zarc_risco: int = 30             # nível de risco do ZARC aceito (20, 30 ou 40); SUPOSIÇÃO a decidir
    zarc_solo: str = "qualquer"      # 'qualquer', 'todos', ou solo específico: 'arenoso', 'medio', 'argiloso'

    def __post_init__(self):
        if self.ciclo_modo not in CICLO_MODOS:
            raise ValueError(f"ciclo_modo deve ser um de {CICLO_MODOS}")
        if self.chuva_modo not in CHUVA_MODOS:
            raise ValueError(f"chuva_modo deve ser um de {CHUVA_MODOS}")
        for par in self.ciclo_override:
            if len(par) != 2 or not isinstance(par[0], str) or int(par[1]) < 1:
                raise ValueError("ciclo_override deve ser ((cultura_id, dias>=1), ...)")
        if self.bloco_ranking not in ("principal", "completo"):
            raise ValueError("bloco_ranking deve ser 'principal' ou 'completo'")
        if not 0 <= self.risco_max < 1:
            raise ValueError("risco_max deve estar em [0, 1)")
        if self.passo_inicio_dias < 1 or self.n_sorteios < 100 or self.top_n < 1 or self.min_anos < 1:
            raise ValueError("passo_inicio_dias, n_sorteios, top_n e min_anos devem ser positivos (n_sorteios >= 100)")
        if not 0 <= self.percentil_baixo < self.percentil_alto <= 100:
            raise ValueError("percentis inválidos")
        if self.zarc_risco not in (20, 30, 40):
            raise ValueError("zarc_risco deve ser 20, 30 ou 40")
        if self.zarc_solo not in ("qualquer", "todos", "arenoso", "medio", "argiloso"):
            raise ValueError("zarc_solo deve ser 'qualquer', 'todos', 'arenoso', 'medio' ou 'argiloso'")
        if self.dirichlet_alfa <= 0:
            raise ValueError("dirichlet_alfa deve ser > 0")

    def suposicoes(self) -> list[str]:
        ciclo = {"min": "o ciclo MÍNIMO (ciclo_min_dias)", "max": "o ciclo MÁXIMO (ciclo_max_dias)",
                 "medio": "o PONTO MÉDIO entre ciclo_min_dias e ciclo_max_dias"}[self.ciclo_modo]
        chuva = ("chuva acumulada durante o ciclo" if self.chuva_modo == "ciclo"
                 else "chuva dos 365 dias desde o início (proxy de chuva anual)")
        pesos = (f"Dirichlet(alfa={self.dirichlet_alfa:g}) sobre os critérios" if self.ordem_pesos is None
                 else f"Dirichlet(alfa={self.dirichlet_alfa:g}) ordenado conforme {list(self.ordem_pesos)}")
        return [
            f"SUPOSIÇÃO (decisão do usuário): duração do ciclo = {ciclo}. O ciclo real não é conhecido; os extremos do "
            "EcoCrop são largos (dezenas a centenas de dias).",
            f"SUPOSIÇÃO: inícios de plantio a cada {self.passo_inicio_dias} dias desde 1º/jan, avaliados em todos os anos "
            f"{self.ano_ini}-{self.ano_fim} com ciclo completo (sem preencher dados faltantes).",
            f"SUPOSIÇÃO: chuva comparada à faixa EcoCrop como {chuva}. Se a faixa do EcoCrop for anual (não verificado), "
            "ciclos curtos ficam penalizados.",
            "Nota de adequação por início e ano = mínimo entre a nota de temperatura (média do ciclo) e a de chuva "
            "(fator mais limitante; ideia do modelo EcoCrop descrito no README do OpenCLIM, reimplementada, sem copiar código). "
            "A melhor janela é o início com maior adequação média entre anos.",
            f"SUPOSIÇÃO (decisão do usuário): nível de risco = até {self.risco_max:.0%} dos anos com nota 0 para a cultura "
            "seguir 'viável'. Não é o risco do ZARC (que mede perda de produtividade).",
            f"Incerteza (estilo SMAA-2, numpy): {self.n_sorteios} sorteios, semente {self.semente}. Sorteia pesos ({pesos}), "
            "lacunas (nota desconhecida ~ Uniforme[0,1], não removida nem premiada) e o ano do clima. Não é intervalo de "
            "confiança nem chance de dar certo na roça.",
            *( [f"SUPOSIÇÃO (decisão do usuário): ZARC LIGADO (risco {self.zarc_risco}, solo '{self.zarc_solo}'): início de plantio "
                "fora dos decêndios indicados recebe nota 0; cultura sem ZARC usa janela APROXIMADA (união das culturas anuais com ZARC no município)."]
               if self.usar_zarc else [] ),
            "SUPOSIÇÃO: pesos sorteados NÃO são preferência de ninguém; os pesos-base do motor são proposta de projeto.",
            *([f"SUPOSIÇÃO (prioridade do agricultor): as alternativas foram escolhidas pelo bloco '{self.bloco_ranking}'."]
              if self.bloco_ranking != "principal" else []),
            f"SUPOSIÇÃO: empate técnico = intervalos de score p{self.percentil_baixo:g}-p{self.percentil_alto:g} que se "
            "sobrepõem. Sem desempate alfabético: empate exato divide a posição igualmente.",
        ]
