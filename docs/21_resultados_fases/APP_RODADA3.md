# App, rodada 3 (2026-11-14): solo ponderado, nomes oficiais, cartão do município, zoom do mapa

Testes: `tests/test_app.py test_mvp.py test_risco_solo.py test_extremos.py test_balanco_hidrico.py test_renda.py test_rotacao.py test_cartao.py test_nomes_ibge.py test_coleta_power.py test_api.py` com `-W error`: 107 passaram.
Tempo por seleção (AppTest, máquina local): primeira execução 10,1 s (carga fria); marcar o zoom 0,53 s; marcar fundo liso 0,64 s; trocar de município 1,01 s.

## 1. Solo: média ponderada pela espessura e aviso de pixels
- Lugar único da conta: `src/culturas/risco_solo.py` (`ESPESSURAS_CM` 5/10/15 cm, `media_ponderada_camadas`, `solo_de_linha`). `mvp.solo_estimado` e `montar_tabela_pontos` usam essa função; `_solo_de_linha` foi removida (teste confere que não existe mais).
- `solo_estimado` agora devolve `fracao_pixels_validos`, `pixel_central_valido` e `aviso_pixels`. Limite: `mvp.LIMITE_FRACAO_PIXELS = 0,5` (janela com menos da metade dos pixels válidos; critério da auditoria do SoilGrids, SOILGRIDS.md parte 1). Pixel central inválido com cobertura boa tem aviso mais fraco. Petrolina-PE (5% da janela) sai com "Poucos pixels do mapa de solo..." na seção da rotação (st.warning) e no cartão.
- Efeito esperado (medido na auditoria, não refeito aqui): argila −1,2 pp em média, soc +1,6 g/kg a menos pela média simples; a classe SiBCS de 1 ponto muda. Não reavaliei os 195 pontos.
- Textura "arenoso" continua nunca saindo do estimado (argila mínima 15,1%): achado 3 da auditoria, não alterado. Cortes 15/35: fonte ainda não verificada.

## 2. Nomes oficiais (D4)
- `src/coleta/nomes_ibge.py` (`python -m src.coleta.nomes_ibge [--dry-run]`): lê `https://servicodados.ibge.gov.br/api/v1/localidades/estados/23/municipios` e grava `nome` em `data/processed/pontos.csv`. Só usa o nome oficial se o código `ibge` é do CE, existe na API e o nome sem acento bate com o id; senão mantém o derivado e lista o motivo.
- Rodada real: 195 pontos; 58 com nome diferente do derivado (acento); `sobral_ce` sem código IBGE (DU8) mantém "Sobral (CE)". As outras colunas ficaram idênticas (conferido por comparação de texto com a cópia anterior). `gravar_pontos` (`src/coleta/power.py`) já preservava colunas extras; ganhou teste para `nome`.
- `mvp.nome_do_ponto` usa `nome` de `pontos.csv` quando existe (lê o arquivo de `SULCO_DADOS_DIR`), senão deriva do id; a lista de municípios ordena sem considerar acento. A derivação ficou em `nomes_ibge.nome_derivado` (mvp importa de lá). `tests/test_mvp.py` agora espera "Várzea Alegre (CE)".
- O CE tem 184 pontos; os outros 11 (PE, PB, RN, PI, BA) continuam com nome sem acento (a API consultada é só da UF 23). Estender para as outras UFs é trocar a lista de UFs; não feito por pedido.

## 3. Cartão do município (AP1)
- `src/app/cartao.py`: `montar_cartao` -> `cartao_html` (A4, `@page`, sem script, sem link) e `cartao_pdf` (fpdf2 2.9.0, uma página; fonte Helvetica padrão, só latin-1: setas e símbolos viram ASCII). Sem `fpdf2` o PDF some e o HTML continua (a tela avisa).
- Conteúdo, todo das funções do app: local; época típica de solo nu e de estresse (frases do diagnóstico, mais a confiança); melhor início de plantio da cultura atual e épocas dentro do ciclo; os 3 caminhos da rotação com pontuação, faixa, chance de ficar entre as 3 melhores, empate técnico e lacunas; risco de solo e solo estimado (com o aviso de pixels); "o que levar ao técnico" (4 itens fixos sem número + até 3 riscos de revisão do motor); "A avaliar com técnico local."
- Tela: seção "6. Cartão do município" com botões de download (HTML e PDF), usando `calc` e a rotação já em cache da tela.
- Testes (`tests/test_cartao.py`): lacunas, empate e aviso presentes; texto não contém "rende mais"/"garante"; todo número do texto existe nos dados de origem (tolerância de arredondamento; também como %); aviso de Petrolina; HTML e PDF de uma folha; dados ausentes viram LACUNA. Amostra de 8 municípios x 2 culturas (prioridade solo): todos com PDF de 1 página.
- Dependência nova: `fpdf2==2.9.0` (PyPI, versão conferida; traz fonttools e Pillow) acrescentada a `requirements.txt` e instalada no `.venv`. Opcional em tempo de execução.
- Limitação: o cartão mostra o resultado de uma amostragem Monte Carlo (n_sorteios do app); a mediana pode variar na casa decimal entre execuções com n diferente.

## 4. Zoom órbita -> município e mapa sem internet
- `src/app/mapa_vista.py`. Caixa "Aproximar do município escolhido" (desligada por padrão; `SULCO_ABERTURA_ZOOM=1` liga para demonstração; testes não definem a variável). Ligada: vista centrada no município, zoom 9, `transitionDuration` 2500 ms.
- Honestidade: o deck.gl anima da vista anterior (visão dos 195 pontos, zoom 5,6) para a nova; NÃO é uma abertura do Brasil inteiro e eu NÃO vi a animação num navegador, só testei os parâmetros da vista e que a tela não quebra. A abertura "Brasil -> município" de verdade exigiria duas renderizações em sequência; não feita.
- AP2: caixa "Estou sem internet (fundo liso)" põe um retângulo cinza atrás dos pontos para dar contraste quando o fundo do mapa (baixado) não carrega; a legenda do mapa explica. O fundo do mapa em si não funciona offline (limite do Streamlit/pydeck); os pontos e todo o resto sim.
