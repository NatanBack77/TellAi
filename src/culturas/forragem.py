"""Valor forrageiro (palma, sorgo, milheto): REGISTRO DE LACUNA com o que foi lido nos PDFs do acervo (docs_rag/), página e trecho copiado.

Resultado da leitura (pdftotext, 2026-11-13): os PDFs do MAPA/Embrapa trazem a produção de biomassa de sorgo, milheto e palma SÓ em gráficos
de barras (Figura 1, p. 4 de mapa_2021_forrageiras_semiarido.pdf) SEM rótulos numéricos; os eixos são inconsistentes (legenda 'kg MS/ha' e
'kg MV/ha' no eixo, e a legenda da figura diz 'kg de massa verde' para cactáceas). Ler a altura da barra seria ESTIMAR: por regra do projeto,
NÃO entra valor. Logo o critério 'valor forrageiro' fica LACUNA e NÃO entra na tabela de culturas (que exige número no trecho).
O único número lido sobre sorgo/milheto é o PONTO DE COLHEITA PARA SILAGEM (dias), que NÃO é valor forrageiro (é manejo); é registrado à parte.
"""
from __future__ import annotations

ARQ_MAPA = "mapa_2021_forrageiras_semiarido.pdf"
ARQ_CARD = "embrapa_caprinos_cardapio_forrageiro.pdf"

AVISO = ("Valor forrageiro (produção de biomassa, proteína, digestibilidade) de palma, sorgo e milheto: LACUNA. Os PDFs do acervo só trazem a "
         "produção em gráfico sem números; o app não lê altura de barra nem estima. Consultar o portal 'Forrageiras' / 'Orçamento forrageiro' "
         "da Embrapa com técnico local.")

LIDO = [
    {"cultura": "sorgo", "arquivo": ARQ_MAPA, "pagina": 3,
     "trecho": "As forrageiras anuais avaliadas foram cultivares de sorgo (BSS Ponta Negra e BRS 658), milho (BRS Gorutuba, BRS 2022 e Bandeirante) e milheto (IPA Bulk e BRS 1301)",
     "numero_forragem": None, "observacao": "cita as cultivares avaliadas; sem valor numérico de produção no texto"},
    {"cultura": "palma", "arquivo": ARQ_MAPA, "pagina": 3,
     "trecho": "as cactáceas (palma miúda, orelha de elefante africana, orelha de elefante mexicana, IPA-Sertânia e palma gigante), populares nos períodos de longa seca",
     "numero_forragem": None, "observacao": "sem valor numérico no texto"},
    {"cultura": "sorgo/milheto/palma", "arquivo": ARQ_MAPA, "pagina": 4,
     "trecho": "Figura 1: Resultados parciais de produção das gramíneas (kg de massa seca) e das cactáceas (kg de massa verde) por hectare.",
     "numero_forragem": None, "observacao": "gráficos de barras sem rótulos; eixos/legendas inconsistentes (MS x MV); NÃO lido como número"},
    {"cultura": "sorgo/milheto", "arquivo": ARQ_CARD, "pagina": 9,
     "trecho": "no sorgo e no milheto esse ponto é quando pelo menos metade da panícula estiver madura (entre 85 a 100 dias depois do plantio, a depender da variedade utilizada)",
     "numero_forragem": None, "observacao": "85-100 dias = ponto de colheita para silagem (manejo), NÃO é valor forrageiro; ciclo da tabela continua vindo do EcoCrop"},
]
CULTURAS = ("palma", "sorgo", "milheto")


def lacunas_forragem() -> list[dict]:
    """Uma lacuna por cultura (palma, sorgo, milheto), com as passagens lidas que a sustentam."""
    return [{"cultura": c, "criterio": "valor_forrageiro", "valor": None, "lacuna": True,
             "motivo": "produção só em gráfico sem números nos PDFs do acervo; sem valor lido, nada é estimado",
             "lido": [x for x in LIDO if c in x["cultura"]]} for c in CULTURAS]
