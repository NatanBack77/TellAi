"""Contrato das 10 etapas do plano de plantio (docs/34_PLANO_DE_PLANTIO.md): números, nomes e rótulos em linguagem simples.

Os nomes e a ordem vêm do usuário e não mudam. Etapas 2 e 3 vêm do motor (dado próprio); as demais, do dado curado com fonte (`data/plano/plano_plantio.csv`).
"""
from __future__ import annotations

ETAPAS: list[tuple[int, str, str, str]] = [
    # (número, slug estável, título, origem)
    (1, "introducao", "Introdução ao Plantio", "curado"),
    (2, "recomendacao", "Recomendação de Plantação", "motor"),
    (3, "clima_epoca", "Clima e Época de Plantio", "motor"),
    (4, "preparacao_solo", "Preparação do Solo", "curado"),
    (5, "semeadura", "Semeadura e Plantio", "curado"),
    (6, "irrigacao_agua", "Irrigação e Cuidados com a Água", "curado"),
    (7, "adubacao", "Adubação e Nutrição", "curado"),
    (8, "desenvolvimento", "Desenvolvimento e Manutenção", "curado"),
    (9, "colheita", "Colheita", "curado"),
    (10, "pos_colheita", "Pós-colheita e Armazenamento", "curado"),
]
ETAPAS_CURADAS = {n for n, _, _, o in ETAPAS if o == "curado"}
STATUS = ("verificado", "lacuna", "nao_se_aplica")

# Termos que NUNCA podem aparecer no valor mostrado ao agricultor (produto, defensivo, fumigação). Regra do produto (docs/30, docs/32).
PROIBIDOS = (r"inseticida", r"herbicida", r"fungicida", r"acaricida", r"nematicida", r"agrot[óo]xico", r"defensivo", r"expurg", r"fumig",
             r"monocrotof", r"clorpirif", r"atrazina", r"treflan", r"alaclor", r"trifluralin", r"piretr[óo]ide", r"carbamato", r"glifosato")

# Rótulos em linguagem simples. O que não está aqui cai no padrão (troca "_" por espaço).
ROTULOS: dict[str, str] = {
    "finalidade": "Para que serve", "importancia_regional": "Importância na região", "vantagem_semiarido": "Vantagem no semiárido",
    "limitacao_principal": "Principal limitação",
    "solo_exigencia": "Solo que a cultura pede", "solo_evitar": "Solo a evitar", "solo_textura_adequada": "Textura de solo mais adequada",
    "ph_ideal": "pH ideal do solo", "preparo_metodo": "Como preparar o solo", "preparo_profundidade_aracao": "Profundidade da aração",
    "preparo_plantio_direto": "Plantio direto", "analise_de_solo_e_calagem": "Análise de solo e calagem",
    "analise_de_solo_orientacao": "Análise de solo", "solo_exigencia_e_preparo": "Solo e preparo",
    "espacamento": "Espaçamento", "espacamento_entre_linhas": "Espaço entre as linhas", "espacamento_sequeiro": "Espaçamento no sequeiro",
    "espacamento_tradicional": "Espaçamento tradicional", "espacamento_adensado": "Espaçamento adensado",
    "espacamento_fileira_simples": "Espaçamento em fileira simples", "espacamento_porte_ereto": "Espaçamento (porte ereto)",
    "espacamento_cultivar_ramificada": "Espaçamento (cultivar ramificada)", "espacamento_cultivar_nao_ramificada": "Espaçamento (cultivar não ramificada)",
    "espacamento_convencional_x_reduzido": "Espaçamento convencional e reduzido", "espacamento_e_densidade": "Espaçamento e densidade",
    "espacamento_linha_x_cova": "Espaçamento entre linhas e covas", "espacamento_no_experimento": "Espaçamento usado em experimento",
    "espacamento_densidade_semente": "Espaçamento, densidade e semente",
    "densidade_plantas_ha": "Plantas por hectare", "densidade_irrigado": "Plantas por hectare (irrigado)", "plantas_por_metro_de_linha": "Plantas por metro de linha",
    "semente_kg_ha": "Semente por hectare", "profundidade_semeadura": "Profundidade da semeadura", "inoculacao_referencia": "Inoculação (referência da fonte)",
    "consorcio_com_milho": "Consórcio com milho", "sementes_por_metro_consorcio_milho": "Sementes por metro no consórcio com milho",
    "kc_inicial": "Coeficiente da cultura, fase inicial (Kc)", "kc_medio": "Coeficiente da cultura, fase média (Kc)", "kc_final": "Coeficiente da cultura, fase final (Kc)",
    "kc_inicial_ano1": "Kc inicial (1º ano)", "kc_medio_ano1": "Kc médio (1º ano)", "kc_final_ano1": "Kc final (1º ano)",
    "kc_inicial_medio_final": "Coeficiente da cultura (Kc)", "fase_critica_deficit_hidrico": "Fase crítica à falta d'água",
    "kc": "Kc (inicial · médio · final)", "kc_ano1": "Kc no 1º ano (inicial · médio · final)",
    "adubacao_cobertura": "Adubação de cobertura", "adubacao_organica_importancia": "Adubação orgânica", "adubacao_quimica_parcelamento": "Parcelamento do adubo químico",
    "adubacao_referencia": "Adubação (referência da fonte)", "adubacao_usada_no_experimento": "Adubação usada em experimento",
    "adubo_organico_referencia": "Adubo orgânico (referência da fonte)", "base_da_calagem": "Base para a calagem",
    "base_da_recomendacao": "Em que se baseia a recomendação", "calagem_antecedencia": "Quando aplicar o calcário",
    "calagem_referencia": "Calagem (referência da fonte)", "calcario_limite_referencia": "Limite de calcário (referência da fonte)",
    "exigencia_nutrientes_referencia": "O que a planta retira do solo (referência da fonte)", "fosforo_referencia": "Fósforo (referência da fonte)",
    "resposta_ao_nitrogenio": "Resposta ao nitrogênio",
    "fase_duracao_dias": "Duração das fases", "fases_fenologicas": "Fases da planta", "estadio_V5": "Estádio V5", "pcc_daninhas": "Período crítico do mato",
    "plantas_daninhas_criticas": "Mato mais problemático", "capina": "Capina", "capina_momento": "Quando capinar", "desbaste": "Desbaste", "amontoa": "Amontoa",
    "praga": "Praga", "praga_sintoma": "Sinal de ataque de praga", "praga_manejo_cultural": "Manejo cultural de pragas", "doenca": "Doença",
    "doenca_manejo": "Manejo de doença", "doenca_manejo_cultural": "Manejo cultural de doença",
    "colheita_indicador": "Como saber que é hora de colher", "colheita_dias_apos_plantio": "Dias até a colheita", "colheita_metodo": "Como colher",
    "colheita_metodo_pequenos_produtores": "Como colhem os pequenos produtores", "colheita_cuidados": "Cuidados na colheita", "colheita_umidade": "Umidade na colheita",
    "colheita_perdas": "Perdas na colheita", "ciclo_grupos_de_maturacao": "Grupos de maturação", "ciclo_ate_floracao_plena": "Ciclo até a floração plena",
    "uso_dos_graos": "Uso dos grãos",
    "secagem_metodo": "Como secar", "secagem_local": "Onde secar", "secagem_cuidados": "Cuidados na secagem", "secagem_umidade_alvo": "Umidade final da secagem",
    "secagem_temperatura_maxima": "Temperatura máxima na secagem", "umidade_para_descascar": "Umidade para descascar",
    "umidade_para_colheita_sem_secagem": "Umidade para colher sem secar", "umidade_de_colheita_sem_secagem": "Umidade para colher sem secar",
    "umidade_que_permite_aeracao_no_lugar_de_secagem": "Umidade que permite aerar em vez de secar",
    "umidade_referencia_comercializacao": "Umidade de referência na venda", "armazenamento_umidade_segura": "Umidade segura para guardar",
    "armazenamento_modo": "Como guardar", "armazenamento_condicoes": "Condições do armazém", "embalagem": "Embalagem", "beneficiamento": "Beneficiamento",
    "praga_armazenamento": "Praga do grão guardado", "manejo_preventivo": "Prevenção no armazém", "monitoramento_armazem": "Vigilância no armazém",
    "contaminante_critico": "Contaminante a vigiar", "conservacao_das_raizes_no_campo": "Conservar as raízes no campo",
    "conservacao_pos_colheita": "Conservar depois da colheita", "ramas_de_plantio_guardar": "Guardar as ramas de plantio",
    "tempo_armazenamento": "Tempo de armazenamento", "comercializacao_preco": "Preço e venda",
}


# "A resposta objetiva" de cada etapa: até 3 itens que a tela mostra primeiro; o resto fica em "detalhes".
# Ordem = prioridade; casa por prefixo do atributo (um item por prefixo). Sem casamento, valem os 3 primeiros itens.
DESTAQUES: dict[int, tuple[str, ...]] = {
    1: ("finalidade", "importancia_regional", "limitacao_principal", "vantagem_semiarido"),
    2: ("cultura_recomendada_1", "cultura_recomendada_2", "cultura_recomendada_3"),   # as 3 plantas mais indicadas para o local e o solo
    3: ("janela_zarc", "estacao_chuvosa", "ciclo_cultura"),
    4: ("solo_exigencia", "ph_ideal", "solo_textura_adequada", "preparo_metodo", "preparo_plantio_direto"),
    5: ("espacamento", "densidade_plantas_ha", "semente_kg_ha", "profundidade_semeadura"),
    6: ("kc", "fase_critica_deficit_hidrico"),
    7: ("base_da_recomendacao", "calagem_antecedencia", "fosforo_referencia", "adubo_organico_referencia", "calagem_referencia"),
    8: ("fase_duracao_dias", "pcc_daninhas", "capina"),
    9: ("colheita_indicador", "colheita_dias_apos_plantio", "colheita_umidade"),
    10: ("secagem_umidade_alvo", "armazenamento_umidade_segura", "umidade_para_colheita_sem_secagem", "secagem_metodo", "armazenamento_modo"),
}
MAX_DESTAQUES = 3


def marcar_destaques(etapa: int, itens: list[dict]) -> None:
    """Põe `destaque` True/False em cada item (até MAX_DESTAQUES). Não reordena e não inventa nada."""
    escolhidos: list[int] = []
    for pref in DESTAQUES.get(etapa, ()):
        i = next((k for k, it in enumerate(itens) if k not in escolhidos and it["atributo"].startswith(pref)), None)
        if i is not None:
            escolhidos.append(i)
        if len(escolhidos) == MAX_DESTAQUES:
            break
    if not escolhidos:
        escolhidos = list(range(min(MAX_DESTAQUES, len(itens))))
    for k, it in enumerate(itens):
        it["destaque"] = k in escolhidos


import re as _re

# "… em data/culturas/x.csv", "… via data/…/y.csv", "(arquivo.parquet)": caminho interno do projeto nunca vai para a tela.
_CAMINHO = _re.compile(r"\s*(?:\b(?:via|em|de|no arquivo)\s+)?[\w./\\-]*(?:\bdata[/\\]|\.csv|\.parquet|\.json|plano_staging|docs_rag)[\w./\\-]*", _re.I)


def limpar_caminhos(texto: str) -> str:
    """Remove referências a arquivos internos de um texto vindo do motor (a fonte continua legível: 'EcoCrop (FAO), faixa de ciclo')."""
    return _re.sub(r"\s{2,}", " ", _CAMINHO.sub("", texto)).strip(" ,;")


def rotulo(atributo: str) -> str:
    return ROTULOS.get(atributo) or atributo.replace("_", " ").capitalize()
