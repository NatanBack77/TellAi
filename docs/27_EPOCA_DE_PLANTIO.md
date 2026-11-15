# 27. Época de plantio no motor (2026-11-14)

## Época de plantio

**Problema.** Com chuva de 365 dias (faixa anual do EcoCrop) e ciclo FAO-56, a chuva fica quase igual para qualquer início e só a temperatura distingue as datas. A "melhor época" do milho foi de dezembro para abril a julho (deslocamento médio de ~150 dias; 15 de 15 municípios, ver `docs/21_resultados_fases/CICLO_FAO_CHUVA_ANUAL.md`). Início em julho no Ceará não é recomendação agronômica.

**Decisão (usuário/coordenação).** A VIABILIDADE da cultura continua pela chuva anual (EcoCrop). A ÉPOCA vem:
1. do **ZARC** quando existe indicação para o município e a cultura (decêndios com risco até o nível escolhido, padrão 30; solo conforme `src/culturas/zarc.py`);
2. quando **não há ZARC** (guandu, sorgo, adubos verdes, ponto sem código IBGE ou fora do Ceará): uma **janela aproximada pela adequação do ciclo**, rotulada "janela aproximada, sem zoneamento oficial".

**Implementação.**
- `Parametros.epoca_modo = "zarc_ou_ciclo"` (novo padrão); `"anual_legado"` reproduz o comportamento anterior (testes de reprodução mantidos).
- `Parametros.usar_zarc` passou a **True** por padrão no motor (antes só o app ligava). Só age em pontos com IBGE do Ceará e cultura mapeada; fora disso vale o ciclo e isso é declarado.
- A adequação para escolher a época é `mínimo(nota de temperatura, nota de chuva anual, atendimento hídrico do ciclo)`. O atendimento hídrico é `chuva do ciclo / demanda_hidrica_mm_ciclo` da tabela, limitado a 1 (7 culturas têm demanda na tabela: milho, feijão comum, sorgo, milheto, algodão, amendoim, girassol). Sem demanda na tabela (guandu, mandioca, mamona etc.): chuva do ciclo relativa à do melhor início do próprio local (SUPOSIÇÃO declarada, `epoca_agua = relativa_ao_melhor_inicio`).
- Dentro da janela do ZARC, a mesma adequação do ciclo escolhe o decêndio. Fora dela a nota é 0 (como já era).
- Só a escolha do início muda: a nota usada no ranking continua sendo `mínimo(temperatura, chuva anual)` no início escolhido.
- `janela_plantio` agora traz `epoca_fonte` (`zarc` | `ciclo_aproximado`; no modo legado `zarc_aproximada_anuais` | `anual_legado_sem_zarc`), `epoca_rotulo` (texto para o usuário) e `epoca_detalhe`/`epoca_motivo`. Se o ZARC não indica nenhum decêndio ao risco pedido, `epoca_sem_indicacao = true` e o rótulo diz que a data é apenas formal.
- Arquivos: `src/culturas/parametros.py`, `src/culturas/ciclo.py` (`_adequacao_epoca`, `resumir`), `src/culturas/motor.py` (`_origem_epoca`), `src/pipeline/gerar_cenarios.py` (`--epoca-modo`).

**Verificação com dados** (`python -m experimentos.epoca_plantio.verificar`; saída `experimentos/epoca_plantio/saida/epoca_verificacao.csv`; 15 municípios do CE por quantis de chuva anual, 16 culturas, 240 pares; clima 2001-2024).
- "Estação chuvosa" aqui é um critério de checagem NOSSO: os 4 meses consecutivos de maior chuva média do local + o mês anterior. Não é norma agronômica.

| Origem da época | pares | início dentro do ZARC | início na estação chuvosa |
|---|---|---|---|
| `zarc` (11 culturas) | 165 | 98,8% (163 de 165) | 98,8% |
| `ciclo_aproximado` (5 culturas sem ZARC) | 75 | não se aplica | 80,0% (60 de 75) |

- Milho e demais culturas com ZARC agora começam em janeiro ou fevereiro (feijão comum e mamona também em março; palma e mandioca janeiro/dezembro), contra abril a setembro no modo legado (ex.: milho: abr, jun, jul, mai, set). O deslocamento absurdo para julho sumiu.
- **Divergências (não escondidas):**
  - 2 pares de 165 com ZARC fora do ZARC: girassol em Aurora e Aracoiaba. O ZARC não indica nenhum decêndio ao risco 30 nesses dois municípios; o motor mostra a cultura como inviável e a data (30/06) é só formal (`epoca_sem_indicacao`).
  - 15 de 75 pares do ciclo aproximado ficam fora da estação chuvosa: **guandu** (outubro a dezembro em 10 de 15 municípios; ciclo de 228 dias) e feijão-de-porco (out/nov/dez em 3), mucuna (dez em 1), sorgo (nov em 1). Causa: sem demanda na tabela, ganha o início cujo ciclo longo acumula mais chuva, o que antecipa o plantio para antes das chuvas. É limitação da regra "janela aproximada"; para guandu a época deve ser tratada como dúvida e confirmada com técnico. Os meses fora do bloco chuvoso estão na coluna `meses_chuvosos` do CSV.
  - A adequação média no início escolhido ficou até 0,03 menor em média que a do modo legado (esperado: antes o início era o máximo da adequação anual, sem sentido agronômico).
- Meses do ZARC por cultura (união nos 15 municípios): milho, feijão comum e mandioca jan-mar; feijão-caupi, algodão, amendoim jan-abr; milheto e mamona jan-mai; gergelim jan-mai; palma nov-mar. O início escolhido ficou sempre dentro desses meses (exceto os 2 casos acima).

**Testes.** Atualizados `tests/test_zarc_motor.py` (padrão novo; legado e "desligado" testados com parâmetros explícitos) e acrescentados 4 testes de época. Ver o fim deste arquivo para o resultado da rodada.

**Alertas.** `experimentos/fao_melhorias/exp5_antes_depois.py` usa `Parametros()` como "depois": com o padrão novo esse "depois" passa a incluir ZARC e época por ciclo; para reproduzir o relatório antigo use `Parametros(usar_zarc=False, epoca_modo="anual_legado")`.

**Resultado da rodada de testes** (`-W error`; test_culturas, test_ciclo_fao, test_zarc_motor, test_incerteza, test_rotacao, test_pipeline, test_conversa*, test_chat_simples, test_fatos): 521 passaram, 3 falharam, os mesmos 3 que já falhavam (texto dos caminhos em `test_chat_simples` x2 e orçamento de 2500 tokens em `test_fatos`); não os escondi nem alterei. Eles leem `data/processed/cenarios/*.json`, que ainda NÃO foi regerado (ver abaixo).

**Regeração dos dados: pendente.** A escrita em `data/processed/cenarios/` foi negada pelo classificador de permissões (sobrescreveria arquivos versionados já modificados). Os 10 cenários novos (milho como cultura atual, 10 000 sorteios) estão em `/tmp/claude-1000/voz/cenarios_novos/`. Para aplicar: `python -m src.pipeline.gerar_cenarios --pontos <10 ids> --cultura-atual milho` e `python -m src.app.precalculo auditoria` (esta última não foi rodada).
