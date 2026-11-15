"""Parâmetros EXPLÍCITOS do motor (ciclo + incerteza). Todo padrão aqui é SUPOSIÇÃO de projeto, não fato.

Cada padrão depende de decisão do usuário e é escrito em `suposicoes` de cada cenário (ver `Parametros.suposicoes`).
Nenhum valor agronômico mora aqui: faixas de temperatura/chuva e ciclo vêm de data/culturas/tabela_culturas.csv.
"""
from __future__ import annotations

from dataclasses import dataclass

CICLO_MODOS = ("min", "medio", "max")
CHUVA_MODOS = ("ciclo", "anual")
CICLO_FONTES = ("fao", "ecocrop")
SOLO_MODOS = ("sem", "ecocrop")
CONSORCIO_MODOS = ("sem", "rotulo", "desempate")
EPOCA_MODOS = ("zarc_ou_ciclo", "anual_legado")


@dataclass(frozen=True)
class Parametros:
    # --- ciclo e janela (decisão do usuário: ciclo real, data de início) ---
    passo_inicio_dias: int = 10      # grade de inícios: a cada N dias a partir de 1º/jan (10 = 36 decêndios)
    ciclo_modo: str = "medio"        # EcoCrop: 'min', 'medio' (ponto médio) ou 'max' de ciclo_min/max_dias; FAO: linha escolhida / menor / maior linha
    ciclo_fonte: str = "fao"         # 'fao' = Tabela 11 do FAO-56 para as 11 culturas cobertas (outras: EcoCrop); 'ecocrop' = só o EcoCrop (comportamento anterior)
    chuva_modo: str = "anual"        # 'anual' = chuva de 365 dias desde o início (faixa EcoCrop é anual); 'ciclo' = chuva acumulada no ciclo (anterior)
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
    usar_zarc: bool = True           # LIGADO por padrão (decisão 2026-11-14); só age em pontos com código IBGE do Ceará; fora dele vale o ciclo e isso é declarado
    # --- ÉPOCA de plantio (decisão 2026-11-14): viabilidade pela chuva anual (EcoCrop); ÉPOCA pelo ZARC (se houver) ou pelo ciclo ---
    epoca_modo: str = "zarc_ou_ciclo"  # 'zarc_ou_ciclo' = ZARC quando há; senão janela APROXIMADA pela adequação do ciclo (temperatura + chuva do ciclo / demanda)
                                       # 'anual_legado' = comportamento anterior (só chuva anual; sem ZARC usa a união das anuais): mantido para reprodução
    zarc_risco: int = 30             # nível de risco do ZARC aceito (20, 30 ou 40); SUPOSIÇÃO a decidir
    zarc_solo: str = "qualquer"      # 'qualquer', 'todos', ou solo específico: 'arenoso', 'medio', 'argiloso'
    # --- solo na viabilidade (docs/27): 'sem' = padrão (nada muda); 'ecocrop' = pH e textura do SoilGrids contra as faixas do EcoCrop; DESLIGADO por padrão ---
    solo_modo: str = "sem"
    # --- consórcio com respaldo publicado (docs/29): 'sem' = padrão (nada muda); 'rotulo' = evidência (LER observado) na alternativa, sem mexer em nota nem ordem;
    #     'desempate' = rótulo + critério secundário SÓ para empate exato na escolha das alternativas (sem estudo = lacuna, não penalidade); DESLIGADO por padrão ---
    consorcio_modo: str = "sem"

    def __post_init__(self):
        if self.ciclo_modo not in CICLO_MODOS:
            raise ValueError(f"ciclo_modo deve ser um de {CICLO_MODOS}")
        if self.ciclo_fonte not in CICLO_FONTES:
            raise ValueError(f"ciclo_fonte deve ser um de {CICLO_FONTES}")
        if self.epoca_modo not in EPOCA_MODOS:
            raise ValueError(f"epoca_modo deve ser um de {EPOCA_MODOS}")
        if self.chuva_modo not in CHUVA_MODOS:
            raise ValueError(f"chuva_modo deve ser um de {CHUVA_MODOS}")
        for par in self.ciclo_override:
            if len(par) != 2 or not isinstance(par[0], str) or int(par[1]) < 1:
                raise ValueError("ciclo_override deve ser ((cultura_id, dias>=1), ...)")
        if self.solo_modo not in SOLO_MODOS:
            raise ValueError(f"solo_modo deve ser um de {SOLO_MODOS}")
        if self.consorcio_modo not in CONSORCIO_MODOS:
            raise ValueError(f"consorcio_modo deve ser um de {CONSORCIO_MODOS}")
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

    def _suposicoes_epoca(self) -> list[str]:
        z = (f"ZARC LIGADO (risco {self.zarc_risco}, solo '{self.zarc_solo}')" if self.usar_zarc else "ZARC DESLIGADO")
        if self.epoca_modo == "anual_legado":
            return ([f"SUPOSIÇÃO (decisão do usuário): {z}: início de plantio fora dos decêndios indicados recebe nota 0; cultura sem ZARC usa "
                     "janela APROXIMADA (união das culturas anuais com ZARC no município). Modo de época 'anual_legado' (anterior), mantido só para "
                     "comparação: com chuva de 365 dias a época deixa de ser informativa."] if self.usar_zarc else [])
        return [f"SUPOSIÇÃO (decisão do usuário 2026-11-14): a VIABILIDADE segue a chuva anual (faixa do EcoCrop), mas a ÉPOCA de plantio vem do ZARC "
                f"quando existe indicação para o município e a cultura ({z}; decêndios fora da indicação recebem nota 0) e, quando NÃO há ZARC "
                "(cultura sem zoneamento, ponto sem código IBGE ou fora do Ceará), de uma JANELA APROXIMADA pela adequação do ciclo: "
                "mínimo(nota de temperatura, nota de chuva anual, atendimento hídrico do ciclo = chuva do ciclo / demanda da tabela, limitado a 1; "
                "sem demanda na tabela: chuva do ciclo relativa à do melhor início do próprio local). Essa janela é rotulada 'janela aproximada, "
                "sem zoneamento oficial' e NÃO é recomendação agronômica."]

    def suposicoes(self) -> list[str]:
        ciclo = {"min": "o ciclo MÍNIMO", "max": "o ciclo MÁXIMO", "medio": "o ciclo central"}[self.ciclo_modo]
        if self.ciclo_fonte == "fao":
            txt_ciclo = (f"SUPOSIÇÃO (decisão do usuário 2026-11-14): duração do ciclo = {ciclo} da Tabela 11 do FAO-56 (Allen et al. 1998) "
                         "para as 11 culturas que a FAO cobre (linha escolhida por regra única: rótulo 'Arid' da FAO, senão mediana das "
                         "linhas; duração = soma dos 4 estágios). É ciclo de referência de OUTRAS regiões (Califórnia, Mediterrâneo, Nigéria, "
                         "Índia...), não medido no semiárido brasileiro. As culturas sem dado FAO (5, lacuna declarada em "
                         "data/culturas/fao_staging.csv) mantêm o ciclo do EcoCrop (ponto médio entre ciclo_min_dias e ciclo_max_dias; extremos largos).")
        else:
            txt_ciclo = (f"SUPOSIÇÃO (decisão do usuário): duração do ciclo = {ciclo} do EcoCrop (ciclo_min_dias, ciclo_max_dias; ponto médio "
                         "no modo 'medio'). O ciclo real não é conhecido; os extremos do EcoCrop são largos (dezenas a centenas de dias). "
                         "Opção anterior mantida para comparação.")
        chuva = ("chuva dos 365 dias desde o início do plantio (a descrição oficial do EcoCrop na FAO fala em 'annual precipitation'; "
                 "o atendimento hídrico do ciclo, chuva sobre a demanda, fica só como informação, fora do ranking)"
                 if self.chuva_modo == "anual" else "chuva acumulada durante o ciclo")
        pesos = (f"Dirichlet(alfa={self.dirichlet_alfa:g}) sobre os critérios" if self.ordem_pesos is None
                 else f"Dirichlet(alfa={self.dirichlet_alfa:g}) ordenado conforme {list(self.ordem_pesos)}")
        return [
            txt_ciclo,
            f"SUPOSIÇÃO: inícios de plantio a cada {self.passo_inicio_dias} dias desde 1º/jan, avaliados em todos os anos "
            f"{self.ano_ini}-{self.ano_fim} com ciclo completo (sem preencher dados faltantes).",
            f"SUPOSIÇÃO: chuva comparada à faixa EcoCrop como {chuva}."
            + (" Se a faixa do EcoCrop for anual, ciclos curtos ficam penalizados (modo anterior, mantido só para comparação)."
               if self.chuva_modo == "ciclo" else " Ficha oficial do EcoCrop não aberta (login): a leitura 'anual' vem da descrição da base, não da ficha da espécie."),
            "Nota de adequação por início e ano = mínimo entre a nota de temperatura (média do ciclo) e a de chuva "
            "(fator mais limitante; ideia do modelo EcoCrop descrito no README do OpenCLIM, reimplementada, sem copiar código). "
            "A melhor janela é o início com maior adequação média entre anos.",
            f"SUPOSIÇÃO (decisão do usuário): nível de risco = até {self.risco_max:.0%} dos anos com nota 0 para a cultura "
            "seguir 'viável'. Não é o risco do ZARC (que mede perda de produtividade).",
            f"Incerteza (estilo SMAA-2, numpy): {self.n_sorteios} sorteios, semente {self.semente}. Sorteia pesos ({pesos}), "
            "lacunas (nota desconhecida ~ Uniforme[0,1], não removida nem premiada) e o ano do clima. Não é intervalo de "
            "confiança nem chance de dar certo na roça.",
            *self._suposicoes_epoca(),
            *( ["SUPOSIÇÃO: solo LIGADO (solo_modo='ecocrop'): pH e textura estimados do SoilGrids (mapa global, não análise) contra as faixas do EcoCrop; a nota de solo limita as notas de temperatura e chuva. Profundidade, fertilidade, salinidade e drenagem NÃO entram (sem dado do local)."]
               if self.solo_modo == "ecocrop" else [] ),
            *( [f"SUPOSIÇÃO: consórcio LIGADO (consorcio_modo='{self.consorcio_modo}'): LER publicado de estudos do semiárido do Nordeste (staging data/culturas/ler_staging.csv) aparece como evidência na alternativa; não entra em nota, pesos nem Monte Carlo."
                + (" No modo 'desempate' o par com estudo vence só um EMPATE EXATO na escolha das alternativas (sem estudo = lacuna, não penalidade); isso não significa que a alternativa seja melhor." if self.consorcio_modo == "desempate" else "")]
               if self.consorcio_modo != "sem" else [] ),
            "SUPOSIÇÃO: pesos sorteados NÃO são preferência de ninguém; os pesos-base do motor são proposta de projeto.",
            *([f"SUPOSIÇÃO (prioridade do agricultor): as alternativas foram escolhidas pelo bloco '{self.bloco_ranking}'."]
              if self.bloco_ranking != "principal" else []),
            f"SUPOSIÇÃO: empate técnico = intervalos de score p{self.percentil_baixo:g}-p{self.percentil_alto:g} que se "
            "sobrepõem. Sem desempate alfabético: empate exato divide a posição igualmente.",
        ]
