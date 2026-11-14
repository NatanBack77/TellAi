"""Gera data/culturas/matriz_rotacao.csv (matriz 'cultura anterior -> cultura seguinte' COM FONTE).

Regras: nenhum grau é digitado de memória. Cada evidência abaixo aponta um arquivo do acervo (docs_rag/), uma página
e um trecho COPIADO do PDF (pdftotext). `matriz_rotacao.verificar_trechos` reextrai a página e confere o trecho.
Par sem evidência no acervo vira LACUNA (esperado: a maioria). Nada de intervalo de retorno por família.

Direção: se a fonte fala em "rotação com X" sem dizer a ordem, `simetrico=sim` e a evidência vale para os dois sentidos.

Uso: python -m src.culturas.construir_matriz_rotacao
"""
from __future__ import annotations

import csv
from pathlib import Path

from .matriz_rotacao import CAMINHO_PADRAO, COLUNAS, culturas_da_tabela

DATA = "2026-11-14"

CAUPI_BOOK = "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf"
REG_CAUPI = ("Meio-Norte/Nordeste do Brasil (Embrapa Meio-Norte, Teresina-PI); livro de perguntas e respostas, "
             "não é estudo de campo com delineamento")
T_REC = "recomendacao_tecnica"
T_REV = "revisao"
T_CAMPO_SA = "artigo_campo_semiarido"
T_CAMPO_OR = "artigo_campo_outra_regiao"

GRAMINEAS = ["milho", "sorgo", "milheto"]


def E(ants, segs, grau, criterio, motivo, arquivo, pagina, trecho, tipo, regiao, simetrico="nao",
      pag_comp="", trecho_comp="", ressalva=""):
    return dict(ants=ants, segs=segs, grau=grau, criterio=criterio, motivo=motivo, arquivo=arquivo, pagina=pagina,
                trecho=trecho, tipo=tipo, regiao=regiao, simetrico=simetrico, pagina_complemento=pag_comp,
                trecho_complemento=trecho_comp, ressalva=ressalva)


EVIDENCIAS = [
    # ---- livro Embrapa Meio-Norte (feijão-caupi): sanidade e nematoides ----
    E(GRAMINEAS, ["feijao_caupi"], "favoravel", "sanidade",
      "Gramíneas são as culturas preferenciais para rotação com o feijão-caupi (aspectos fitossanitários, econômicos e de "
      "aproveitamento de resíduos), em área irrigada por aspersão.",
      CAUPI_BOOK, 136, "as culturas preferenciais para rotação são gramíneas, como milho, sorgo e milheto", T_REC, REG_CAUPI,
      simetrico="sim", pag_comp=136, trecho_comp="irrigada com feijão-caupi? Considerando os aspectos fitossanitários",
      ressalva="A fonte não diz a ordem; vale como rotação entre as duas. Contexto da pergunta: área irrigada."),
    E(["milho", "sorgo"], ["feijao_caupi"], "favoravel", "sanidade",
      "Mancha-bacteriana do caupi: rotação com gramíneas (milho e sorgo) rompe o ciclo da doença porque a bactéria não "
      "ataca essas plantas.",
      CAUPI_BOOK, 173,
      "Também deve ser usada a rotação de cultura, principalmente com gramíneas (milho e sorgo), para romper o ciclo da "
      "doença, uma vez que a bactéria não ataca essas plantas.", T_REC, REG_CAUPI, simetrico="sim",
      pag_comp=173, trecho_comp="Como controlar a mancha-bacteriana do feijão-caupi?"),
    E(GRAMINEAS, ["feijao_caupi"], "favoravel", "sanidade",
      "Murcha/podridão de esclerócio do caupi: rotação com espécies não hospedeiras (gramíneas) é medida de controle.",
      CAUPI_BOOK, 157, "adotar a rotação de cultura com espécies não hospedeiras (gramíneas)", T_REC, REG_CAUPI,
      simetrico="sim", pag_comp=157, trecho_comp="O que é murcha ou podridão de esclerócio do feijão-caupi?",
      ressalva="'Gramíneas' na fonte é genérico; mapeado para milho, sorgo e milheto por serem gramíneas (Poaceae)."),
    E(["feijao_comum", "girassol", "amendoim"], ["feijao_caupi"], "desfavoravel", "sanidade",
      "Fungos de solo do caupi são polífagos e também se alimentam de feijão-comum, girassol e amendoim; as estruturas de "
      "resistência permanecem no solo por longo período.",
      CAUPI_BOOK, 151,
      "Muitos desses patógenos são polífagos, isto é, nutrem-se de outras espécies vegetais, tais como a soja, o "
      "feijão-comum, o girassol e o amendoim", T_REC, REG_CAUPI, simetrico="sim",
      pag_comp=151, trecho_comp="Quais são as principais doenças que atacam o feijão-caupi, causadas por fungos que sobrevivem no solo?",
      ressalva="Risco de patógeno comum, não é medida de perda de produtividade."),
    E(["girassol", "gergelim", "algodao"], ["feijao_caupi"], "neutro", "opcao_de_rotacao",
      "Girassol, gergelim e algodão 'também podem ser rotacionados' com o caupi: opção possível, não a preferencial.",
      CAUPI_BOOK, 136, "As culturas de girassol, gergelim e algodão também podem ser rotacionadas com o feijão-caupi",
      T_REC, REG_CAUPI, simetrico="sim", pag_comp=136, trecho_comp="irrigada com feijão-caupi? Considerando os aspectos fitossanitários",
      ressalva="Sem efeito descrito; 'neutro' aqui significa 'opção citada como possível'."),
    E(["crotalaria_juncea", "mucuna", "milheto", "guandu"], ["feijao_caupi"], "favoravel", "nematoides",
      "Plantas antagonistas aos nematoides (crotalárias, mucuna-preta, milheto, feijão-guandu) são indicadas no manejo de "
      "nematoides em lavoura de caupi.",
      CAUPI_BOOK, 183,
      "As mais utilizadas são: as crotalárias (Crotalaria spectabilis, C. juncea, C. retusa, C. paulina, C. ochroleuca, "
      "entre outras), o cravo-de-defunto (Tagetes spp.), a mucuna-preta (Mucuna pruriens), várias espécies de braquiária "
      "(Brachiaria spp.), o milheto (Penisetum glaucum) e o feijão-guandu (Cajanus cajan)", T_REC, REG_CAUPI,
      pag_comp=183, trecho_comp="Quais são as plantas antagonistas mais indicadas ao manejo dos nematoides em lavoura de feijão-caupi?",
      ressalva="Depende da espécie de nematoide presente (a própria fonte diz isso); não é garantia."),
    E(["milho"], ["feijao_caupi"], "desfavoravel", "nitrogenio",
      "Após cultura que produz muita palha pobre em N (milho), possivelmente o caupi precisa de mais nitrogênio: os "
      "microrganismos absorvem o N na decomposição.",
      CAUPI_BOOK, 84,
      "produza muita palha, como milho, capim ou arroz, possivelmente haverá maior necessidade de nitrogênio, pois os "
      "restos culturais dessas plantas são pobres em nitrogênio e, no início de sua decomposição, os microrganismos do "
      "solo absorvem o nitrogênio que estaria disponível para o feijão-caupi", T_REC, REG_CAUPI,
      ressalva="Texto diz 'possivelmente'; é necessidade de adubação, não perda comprovada."),
    E(["feijao_caupi"], ["feijao_caupi"], "desfavoravel", "sanidade",
      "Podridão-radicular-seca do caupi é favorecida depois de cultivos sucessivos de caupi na mesma área.",
      CAUPI_BOOK, 154,
      "Ela é favorecida pelo cultivo em solos compactados e úmidos, sobretudo depois de cultivos sucessivos de "
      "feijão-caupi na mesma área.", T_REC, REG_CAUPI, ressalva="Par da diagonal (repetição); fora dos 240 pares."),
    # ---- Embrapa Meio-Norte: caupi sobre palhada de sorgo no semiárido piauiense ----
    E(["sorgo"], ["feijao_caupi"], "neutro", "sequencia_praticada",
      "Estudo de irrigação do caupi plantado sobre palhada de sorgo no semiárido piauiense; o estudo não compara "
      "antecessoras, só mostra a sequência em uso.",
      "embrapa_meionorte_caupi_plantio_direto_semiarido_piaui.pdf", 3,
      "aplicadas à cultura do feijão-caupi ‘BRS Imponente’, cultivado sobre palhada de sorgo no Semiárido piauiense",
      T_CAMPO_SA,
      "Parnaíba-PI (Semiárido piauiense), Embrapa Meio-Norte",
      ressalva="Sem efeito da antecessora medido; 'neutro' = sequência praticada, sem comparação."),
    # ---- Debiasi et al. (Embrapa Soja): opções de rotação com milho 2a safra ----
    E(["milho"], ["girassol", "sorgo", "milheto"], "neutro", "opcao_de_rotacao",
      "Girassol, sorgo e milheto são citados como espécies que podem ser usadas em rotação com o milho de 2ª safra "
      "(região tropical).",
      "embrapa_debiasi_diversificacao_especies.pdf", 19,
      "O girassol, o sorgo (granífero ou forrageiro), o milheto, ocapim-sudão, o capim-coracana (Eleusine coracana) e as "
      "forrageiras tropicais (Urochloa spp. e Panicum spp.) são exemplos de espécies vegetais que podem ser utilizadas "
      "em rotação com o milho de 2ª safra", T_REC,
      "Centro-Oeste/Brasil tropical (Embrapa Soja; sistemas com soja), não semiárido", simetrico="sim",
      ressalva="Lista de opções, sem efeito medido; sorgo e milheto são gramíneas como o milho (ver Cruz et al.)."),
    E(["milho"], ["algodao"], "neutro", "opcao_de_rotacao",
      "O algodão pode ser usado em rotação com o milho de 2ª safra onde a chuva é bem distribuída (Mato Grosso).",
      "embrapa_debiasi_diversificacao_especies.pdf", 19,
      "o algodão pode ser utilizado em rotação com o milho na 2ª safra", T_REC, "Mato Grosso (Embrapa Soja), não semiárido",
      simetrico="sim", ressalva="Condicionado a chuva bem distribuída; sem efeito medido."),
    E(["feijao_caupi", "milheto"], ["algodao"], "neutro", "opcao_de_rotacao",
      "Caupi e milheto são citados como cultura de verão que pode anteceder o algodão (Mato Grosso).",
      "embrapa_debiasi_diversificacao_especies.pdf", 19,
      "a cultura de verão antecedendo o algodão pode ser a soja (cultivares superprecoces, com ciclo ao redor de 100 "
      "dias), o feijão-caupi (Vigna unguiculata) ou espécies para cobertura do solo, como milheto e as crotalárias",
      T_REC, "Mato Grosso (Embrapa Soja), não semiárido", ressalva="Lista de opções, sem efeito medido."),
    # ---- Cruz et al. (Embrapa Milho e Sorgo) ----
    E(["milho"], ["sorgo", "milheto", "milho"], "desfavoravel", "familia_graminea",
      "Após milho para silagem, repetir milho/sorgo/milheto é viável, mas a fonte diz que exige outra opção para quebrar "
      "o ciclo de plantio de gramíneas.",
      "embrapa_cruz_plantio_direto_sustentabilidade.pdf", 5,
      "Essas alternativas, embora sejam viáveis, necessitam de alguma outra opção para quebrar este ciclo de plantio de "
      "gramíneas.", T_REC, "Sul de Minas Gerais (relato de agricultores, Embrapa Milho e Sorgo), não semiárido",
      pag_comp=5,
      trecho_comp="Alguns agricultores já usam, após o milho para silagem, o plantio de outra safra do próprio milho, "
                  "aveia, plantios de sorgo forrageiro ou de corte e pastejo ou milheto.",
      ressalva="Alerta qualitativo, sem número; milho->milho está na diagonal."),
    E(["algodao", "girassol", "guandu"], ["milho"], "favoravel", "produtividade_seguinte",
      "Em Rio Verde (GO), as maiores produtividades de milho foram sobre palhadas de algodão, girassol, guandu e nabo "
      "forrageiro (Ferreira, 1998, citado).",
      "embrapa_cruz_plantio_direto_sustentabilidade.pdf", 5,
      "lhadas de algodão, girassol, guandu e nabo forrageiro, enquanto que, para a cultura da soja", T_REV,
      "Rio Verde-GO (Cerrado), citando Ferreira (1998)", pag_comp=4,
      trecho_comp="constatou que as maiores produtividades de milho são sobre as pa",
      ressalva="Frase corta entre as páginas 4 e 5 (complemento na pág. 4); sem número e sem delineamento na revisão."),
    # ---- Alvarenga et al. (Informe Agropecuário) ----
    E(["mucuna", "crotalaria_juncea"], ["milho"], "favoravel", "produtividade_seguinte",
      "Milho semeado sobre restos de leguminosas (mucuna cinza, crotalária) rendeu 39,7% a mais que o pousio (ensaio "
      "demonstrativo sem repetição).",
      "embrapa_alvarenga_plantas_cobertura_spd.pdf", 3,
      "Apesar de haver um aumento de 39,7% na produtividade média do milho após o cultivo de leguminosas (mucuna e "
      "crotalária), em relação ao controle", T_CAMPO_OR,
      "Uberlândia/Triângulo Mineiro-MG (Cerrado), Aguiar (1998) citado",
      ressalva="Parcelas demonstrativas sem repetição; a fonte diz que grande parte do N não foi aproveitada. A frase "
               "não diz a espécie de crotalária (a lista de destaque cita C. juncea)."),
    E(["feijao_de_porco"], ["milho"], "favoravel", "produtividade_seguinte",
      "Feijão-de-porco permitiu rendimento de milho em sucessão equivalente ao de 130 kg/ha de N (Santa Maria-RS).",
      "embrapa_alvarenga_plantas_cobertura_spd.pdf", 5,
      "O feijão-de-porco foi a leguminosa que se destacou, pois permitiu um rendimento de grãos de milho em sucessão",
      T_REV, "Santa Maria-RS (Sul), citando Ceretta et al. (1994)",
      ressalva="Clima subtropical; o N de comparação vem da frase seguinte."),
    # ---- PAB (Carvalho et al. 2004) ----
    E(["crotalaria_juncea"], ["milho"], "favoravel", "produtividade_seguinte",
      "Crotalária (sunn hemp) cultivada na primavera aumentou 18,5% a produtividade do milho em sucessão, comparada ao "
      "pousio, em ano de chuva normal.",
      "pab_milho_sucessao_adubos_verdes.pdf", 1,
      "A crotalária cultivada na primavera proporcionou aumento de 18,5% na produtividade do milho em sucessão, "
      "comparada à área de pousio", T_CAMPO_OR,
      "Selvíria-MS (Cerrado), Latossolo", pag_comp=1,
      trecho_comp="The sunn hemp previously grown in spring increased 18.5% the corn yield, compared to the fallow",
      ressalva="'Sunn hemp' lido como Crotalaria juncea (nome comum). Em ano com veranico o preparo convencional rendeu mais."),
    # ---- Pesagro-Rio (revisão) ----
    E(["feijao_de_porco"], ["milho"], "favoravel", "produtividade_seguinte",
      "Leguminosas de cobertura, entre elas o feijão-de-porco, aumentaram o rendimento do milho de 17 a 93% sobre a "
      "testemunha (Spagnollo et al., 2002, citado).",
      "pesagro_rio_rural_rotacao_culturas.pdf", 6,
      "as leguminosas, dentre elas o feijão-de-porco, aumentaram o rendimento do milho de 17 a 93%", T_REV,
      "Sul do Brasil e Sudeste (revisão da Pesagro-Rio)", ressalva="Faixa ampla (17 a 93%); revisão sem delineamento próprio."),
    E(["mucuna"], ["feijao_comum"], "favoravel", "produtividade_seguinte",
      "O rendimento do feijão dobrou com adubação verde de mucuna-preta em relação à sucessão a milho (Arf et al., 1999, "
      "citado).",
      "pesagro_rio_rural_rotacao_culturas.pdf", 6,
      "O rendimento da cultura do feijão dobrou com a utilização da adubação verde com a mucuna preta em relação ao "
      "tratamento em sucessão à cultura do milho", T_REV, "Ilha Solteira-SP (revisão da Pesagro-Rio citando Arf et al.)",
      ressalva="A comparação é com milho (palhada), não com pousio; a revisão não diz 'feijão comum' em Phaseolus."),
    E(["feijao_de_porco"], ["milho", "feijao_comum"], "favoravel", "produtividade_seguinte",
      "Em Campos dos Goytacazes-RJ, as maiores produtividades de milho e feijão comum vieram de sucessões com "
      "feijão-de-porco em semeadura direta (Duarte Jr., 2006, citado).",
      "pesagro_rio_rural_rotacao_culturas.pdf", 12,
      "As maiores produtividades do milho e do feijão comum foram obtidas com as sucessões feijão-de-porco/ "
      "milho/feijão-de-porco/milho e feijão-de-porco/ feijão comum/feijão-de-porco/milho em SSD", T_REV,
      "Campos dos Goytacazes-RJ (revisão citando Duarte Jr., 2006)",
      ressalva="Sequências de 4 cultivos em semeadura direta: o efeito de um só antecessor não está isolado."),
]


def linhas() -> list[dict]:
    ids = culturas_da_tabela()
    achados: dict[tuple[str, str], list[dict]] = {}
    for ev in EVIDENCIAS:
        pares = [(a, s) for a in ev["ants"] for s in ev["segs"]]
        if ev["simetrico"] == "sim":
            pares += [(s, a) for a, s in pares]
        for a, s in dict.fromkeys(pares):
            if a not in ids or s not in ids:
                raise ValueError(f"cultura fora da tabela: {a}, {s}")
            achados.setdefault((a, s), []).append(ev)
    out = []
    for a in ids:
        for s in ids:
            evs = achados.get((a, s))
            if not evs:
                if a != s:
                    out.append({c: "" for c in COLUNAS} | {
                        "anterior": a, "seguinte": s, "grau": "LACUNA",
                        "motivo": "Nenhum documento do acervo local trata este par.", "data_verificacao": DATA})
                continue
            for ev in evs:
                out.append({
                    "anterior": a, "seguinte": s, "grau": ev["grau"], "criterio": ev["criterio"], "motivo": ev["motivo"],
                    "simetrico": ev["simetrico"], "arquivo": ev["arquivo"], "pagina": ev["pagina"], "trecho": ev["trecho"],
                    "pagina_complemento": ev["pagina_complemento"], "trecho_complemento": ev["trecho_complemento"],
                    "tipo_evidencia": ev["tipo"], "regiao_estudo": ev["regiao"], "ressalva": ev["ressalva"],
                    "data_verificacao": DATA})
    return out


def main(destino: Path = CAMINHO_PADRAO) -> int:
    rows = linhas()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} linhas escritas em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
