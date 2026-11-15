# 28. Pesquisa: voz mais humana em português do Brasil (2026-11-14)

Problema: a voz da DeepSeek não foi feita para português (soa estrangeira) e as vozes do navegador soam robóticas.
Este texto compara as opções, diz o que foi testado nesta máquina e como ligar a melhor ao `/voz/falar`.

## Como ler esta pesquisa (confiança)

- **Todas as páginas abaixo foram abertas com a ferramenta WebFetch, que devolve só um RESUMO feito por modelo pequeno.** Por isso todo número de preço/limite está marcado "(resumo)". Antes de decidir com dinheiro, confira na página oficial.
- Onde a página veio cortada ou sem o dado, está escrito **"não li"**. Não preenchi com memória.
- **Qualidade (quão "humana" soa) NÃO foi medida por mim**: eu não ouço áudio. Os WAVs de teste precisam ser escutados por uma pessoa. O que está escrito sobre qualidade é o que as páginas dizem, não opinião minha.

## 1. Tabela comparativa

| Opção | Onde roda | Custo / plano grátis (resumo) | Conta/cartão | Licença | Privacidade (para onde vai o texto) | Peso | Qualidade pt-BR |
|---|---|---|---|---|---|---|---|
| **Piper** (vozes cadu, faber, jeff medium; edresson low) | Aqui, CPU | Grátis | Não | Código GPL-3.0-or-later (pacote `piper-tts` 1.8.0, lido nos metadados); vozes: CC0 (cadu, faber, jeff), CC BY 4.0 (edresson) | Fica na máquina | ~60 MB por voz (lido: 60,3 MB; edresson 60,2 MB) | Não medida. Tem aviso "Missing phoneme" (nasal) ao gerar |
| **Kokoro-82M** (pf_dora, pm_alex, pm_santa) | Aqui, CPU | Grátis | Não | Pesos Apache-2.0 (página oficial, resumo); `kokoro-onnx` sem licença nos metadados (não li o repositório); fonemizador `espeak-ng` é GPL | Fica na máquina | 92 MB (int8) + 28 MB de vozes | Não medida. 3 vozes pt-BR existem (VOICES.md, resumo). Mais lento: ~12 s para ~11,7 s de áudio com a máquina ocupada |
| **Azure AI Speech** | Nuvem | Grátis F0: 0,5 milhão de caracteres/mês neural (resumo). Preço por 1M de caracteres: a página mostrou "$-": não li | Conta Azure (cartão normalmente) | Serviço pago | O texto vai para a Microsoft | 0 | Vozes pt-BR citadas em busca: Francisca, Antonio, Thalita (multilingual), Macério e outras; quais são "HD": **não confirmei** |
| **Google Cloud TTS** | Nuvem | Página oficial: tabela não lida (veio cortada). Terceiro (CostBench) diz 1M de caracteres grátis em Chirp 3 HD a US$ 30/1M, mas outros terceiros divergem: **não confiar sem abrir a página** | Conta Google Cloud com cobrança ligada (resumo) | Serviço pago | Vai para o Google | 0 | Chirp 3 HD existe (30 estilos, sem SSML); nomes pt-BR: não li |
| **Amazon Polly** | Nuvem | Neural: 1M de caracteres/mês nos 12 primeiros meses, depois US$ 16/1M. Generative: 100 mil/mês nos 12 primeiros meses, US$ 30/1M. Standard: 5M/mês, US$ 4/1M (resumo da página de preços) | Conta AWS com cartão | Serviço pago | Vai para a Amazon | 0 | pt-BR: Camila (generative, neural, standard), Vitória (neural, standard), Ricardo (standard), Thiago (neural), Carolina e Leo (generative) (tabela oficial, resumo) |
| **ElevenLabs** | Nuvem | Grátis: 10 mil créditos/mês (~10 mil caracteres) (resumo). Se o plano grátis tem API e uso comercial: a página não diz; a ajuda deu 403 | Conta | Serviço pago | Vai para a ElevenLabs | 0 | Muito citada como a mais natural; **não verifiquei pt-BR nem medi** |
| **OpenAI TTS** | Nuvem | tts-1 US$ 15/1M caracteres; tts-1-hd US$ 30/1M; gpt-4o-mini-tts US$ 0,60/1M tokens de texto + US$ 12/1M tokens de áudio (resumo). Sem plano grátis lido | Conta com crédito | Serviço pago | Vai para a OpenAI | 0 | Não verifiquei pt-BR oficialmente |
| **edge-tts** (pacote NÃO oficial) | Nuvem (serviço "ler em voz alta" do Edge) | Grátis, sem chave | Não | GPL-3.0 (inferido do arquivo gpl-3.0.txt; resumo) | Vai para a Microsoft | pequeno | O projeto é de uma pessoa (`rany2`), **não é da Microsoft**. Usa serviço que a Microsoft não vendeu como API; pode quebrar ou violar termos. **Não recomendo em produto**. Não testei (era nuvem não oficial e eu só testei o que roda local) |
| **Coqui XTTS-v2** | Aqui (pesado) | Grátis | Não | Coqui Public Model License (CPML); a página não diz se uso comercial é permitido: **não baixei** | Local | Grande (não li) | pt está na lista |
| **MMS-TTS por (Meta)** | Aqui | Grátis | Não | **CC-BY-NC 4.0 (não comercial)**: **não baixei** | Local | 36,3 M de parâmetros | Não li limitações |
| **Fish Speech / F5-TTS pt-BR / Sherpa-ONNX** | Aqui | | | **Não pesquisei a fundo** (sem tempo; fica como lacuna) | | | |
| **Voz do celular** (Android "Google Voz"; iOS "Fala avançada") | No aparelho | Grátis | Não | do sistema | Fica no aparelho (a voz offline) | 20 a 200 MB por voz instalada (não li) | Costuma ser melhor que a do navegador de desktop, mas não medi |

### Voz do próprio celular

- Android: Configurações > Acessibilidade > Saída de texto para fala (ou "Instalar dados de voz") e escolher Português (Brasil); a página do Google (resumo) confirma o caminho "Install voice data" e "Text-to-speech output", mas não cita Português nem o nome do pacote. Em muitos aparelhos o menu varia.
- iPhone: Ajustes > Acessibilidade > Conteúdo falado > Vozes > Português (Brasil) > baixar a versão "Aprimorada/Premium". Esse caminho é de memória: **a página da Apple não deu o texto**.
- No navegador a página `/voz` já escolhe uma voz pt-BR do aparelho. O seletor "Qual voz" mostra as instaladas. Dica para o agricultor: instalar a voz de melhor qualidade no celular custa zero e não envia o texto a ninguém.

## 2. Testes de áudio nesta máquina

Ambiente: venv separado `/tmp/claude-1000/voz/venv_tts` (Python 3.14, `piper-tts` 1.8.0, `kokoro-onnx` 0.4.7, `onnxruntime` 1.32). A instalação deu certo; não houve erro. Frase única de teste:

> Oi! Eu sou o assistente automático do Sulco. Entendi que você quer economizar água. Olhando os dados do seu local, o feijão comum e o milheto pedem menos água. Converse com o técnico para confirmar.

Máquina de 8 núcleos, 7 GB, sem GPU e com outros processos rodando (os tempos são do pior caso).

| Amostra (caminho) | Tamanho | Tempo de geração | Duração do áudio |
|---|---|---|---|
| `/tmp/claude-1000/voz/amostras/piper_cadu-medium.wav` | 584 KB | 3,6 s | 13,2 s |
| `/tmp/claude-1000/voz/amostras/piper_faber-medium.wav` | 539 KB | 4,9 s | 12,2 s |
| `/tmp/claude-1000/voz/amostras/piper_jeff-medium.wav` | 547 KB | 6,2 s | 12,4 s |
| `/tmp/claude-1000/voz/amostras/piper_edresson-low.wav` | 527 KB | 1,3 s | 16,5 s (voz "low", 16 kHz; fala lenta) |
| `/tmp/claude-1000/voz/amostras/kokoro_pf_dora.wav` | 559 KB | 11,8 s | 11,6 s |
| `/tmp/claude-1000/voz/amostras/kokoro_pm_alex.wav` | 563 KB | 13,3 s | 11,7 s |
| `/tmp/claude-1000/voz/amostras/kokoro_pm_santa.wav` | 561 KB | 12,5 s | 11,7 s |

Carga do modelo: 1,6 a 3,4 s (Piper), 1,3 s (Kokoro). Carregar uma vez na subida do servidor.

Origem e sha256 (conferidos depois do download):

| Arquivo | URL | sha256 |
|---|---|---|
| pt_BR-cadu-medium.onnx | https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx | d5a662e3f606d5a49dd29ba9ce90c304ae45dd9543f8b0c773bcb0de282499de (igual ao da listagem LFS) |
| pt_BR-faber-medium.onnx | .../pt_BR/faber/medium/pt_BR-faber-medium.onnx | 75e913eb463db0b6ac7ddf68d3e4c9ac19ace36dc3b710a81039b448352b8ffc (igual) |
| pt_BR-jeff-medium.onnx | .../pt_BR/jeff/medium/pt_BR-jeff-medium.onnx | 82ddcdb01a0342f078bd89ce2815eda27185818d15e15f06fb9a72ac3bce94e1 (igual) |
| pt_BR-edresson-low.onnx | .../pt_BR/edresson/low/pt_BR-edresson-low.onnx | de4cecee38b30bb1a6378a337af605d59f0c377df702c6a6752870db8991cd84 (igual) |
| kokoro-v1.0.int8.onnx | https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx | 6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb (sem referência oficial para comparar) |
| voices-v1.0.bin | .../model-files-v1.0/voices-v1.0.bin | bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d (idem) |

Licenças dos dados das vozes Piper (MODEL_CARD abertos): cadu, faber, jeff = CC0 (dataset OHF-Voice/voice-datasets); edresson = CC BY 4.0 (TTS-Portuguese-Corpus; exige citar a autoria). O repositório `rhasspy/piper` está arquivado desde 06/10/2025 e o desenvolvimento foi para `OHF-Voice/piper1-gpl` (resumo).

**Não baixei por licença:** XTTS-v2 (CPML, uso comercial não confirmado) e MMS-TTS (CC-BY-NC). **Não testei:** nuvem (não tenho conta), edge-tts (não oficial), Fish Speech, F5-TTS e Sherpa-ONNX.

**Observações honestas sobre os testes**
- Não ouvi os arquivos. Só confirmei que foram gerados com duração plausível.
- Piper imprimiu "Missing phoneme from id map" para o til nasal: pode haver sons nasais imperfeitos; só o ouvido diz.
- Kokoro é cerca de 3x mais lento que Piper aqui, quase tempo real: para respostas curtas de agricultor é aceitável, mas some a latência do `/chat`.

## 3. Recomendação (ordem)

1. **Testar primeiro (hoje, sem custo): ouvir as 7 amostras** com uma pessoa do público e escolher. Se alguma servir, não precisa pagar nada.
2. **Piper (cadu ou faber) no servidor**: grátis, CC0 nas vozes, dados ficam na máquina, rápido (3 a 5 s). Atenção: o pacote `piper-tts` é GPL-3.0; usar como biblioteca num servidor próprio é comum, mas se for distribuir a imagem Docker com ele, a GPL vale para esse componente. Registrar isso na decisão.
3. **Kokoro (pf_dora)** se o ouvido preferir (pesos Apache-2.0; o fonemizador espeak-ng é GPL).
4. **Voz do celular (Android "Google Voz" / iOS "Aprimorada")** como padrão sem custo e sem enviar texto: bom para quem tem um aparelho recente.
5. **Nuvem só se as locais não bastarem**: Polly neural (Camila/Thiago) ou Azure (Francisca), pelo plano grátis lido. Com o orçamento de US$ 5, a conta é simples: ~US$ 16 por 1 milhão de caracteres (Polly neural); resposta curta tem uns 300 caracteres, então US$ 5 pagam ~300 mil caracteres = ~1000 respostas. Isso é conta de cabeça sobre preço de lista (resumo), não medição.
6. **Evitar**: edge-tts (não oficial, risco de termos), XTTS e MMS (licença não permite o uso).

Privacidade: Piper, Kokoro e voz do celular mantêm o texto local. Qualquer nuvem envia a resposta (que cita município e cultura) para fora; avisar na tela, como já é feito para a DeepSeek.

## 4. Como ligar a melhor opção (Piper) ao `/voz/falar`

Interface atual: `_tts_deepseek(texto, voz="stella") -> bytes` (WAV). O contador de gasto (`chars_fala_dia`) e o PIN seguem iguais.

1. Dependência: `pip install piper-tts` (venv do projeto) e baixar uma voz para `data/modelos_voz/` (não versionar; ~60 MB): `pt_BR-cadu-medium.onnx` e `.onnx.json`. Em Docker, baixar no build e conferir o sha256 da tabela acima.
2. Em `src/api/voz.py`, nova função, mesma interface:

```python
_PIPER = {}

def _tts_piper(texto: str, voz: str = "cadu") -> bytes:   # pragma: no cover - modelo local
    import io, wave
    from piper import PiperVoice
    if voz not in _PIPER:
        _PIPER[voz] = PiperVoice.load(str(RAIZ / f"data/modelos_voz/pt_BR-{voz}-medium.onnx"))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        _PIPER[voz].synthesize_wav(texto, w)
    return buf.getvalue()
```

3. Seletor no servidor: `MOTORES_TTS = {"deepseek": _tts_deepseek, "piper": _tts_piper}`; em `falar`, ler `motor = (corpo or {}).get("motor", "piper")`, rejeitar valor fora da lista (400) e chamar `MOTORES_TTS[motor](fala)`. Piper não cobra: não somar ao custo estimado (somar só caracteres para o limite, ou só contar a chamada). Ainda assim manter o limite de caracteres (protege CPU).
4. Na página (`src/api/pagina_voz.py`): no `<select id="voz">` acrescentar `<option value="piper">Voz do servidor (Piper, sem custo)</option>` e, em `falar()`, enviar `{texto, motor: $('voz').value}` quando o valor for `piper` ou `deepseek`. O aviso de privacidade só precisa aparecer para `deepseek`.
5. Teste: `monkeypatch` de `_tts_piper` como já é feito com `_tts_deepseek`; um teste de que `motor` inválido devolve 400.
6. Fazer só depois de alguém ouvir e aprovar a voz.

## 5. Reconhecimento de fala (ASR) para sotaque regional e ruído

| Opção | Custo/limite (resumo) | Observação |
|---|---|---|
| **Whisper large-v3 / turbo na Groq** | Limites do plano Developer lidos: 20 pedidos/min, 2 mil/dia, 7,2 mil s de áudio/hora, 28,8 mil s/dia, nos dois modelos. A página não mostrou o limite do plano grátis (ver `console.groq.com/settings/limits`). Preço por hora: **não li** (página de preços sem o dado) | Whisper aceita português; precisa de conta e chave; o áudio vai para a Groq |
| **OpenAI** | Whisper e gpt-4o-transcribe US$ 0,006/min; gpt-4o-mini-transcribe US$ 0,003/min (resumo) | Mesma integração por HTTP |
| **faster-whisper local** | Grátis; modelo "small" ou "medium" roda em CPU, mas lento nesta máquina de 7 GB (não testei) | Privacidade total. `large-v3` em CPU de 7 GB é pesado; escolher "small"/"turbo" quantizado |
| **Azure Speech** | Grátis F0: 5 horas de áudio/mês em tempo real (resumo); preço pago: não li | Aceita pt-BR; conta Azure |
| **Google STT / Chirp** | Não li | |

Como integrar: o contrato de `_asr_deepseek(wav) -> {"text", "duration_ms"}` basta; escrever `_asr_groq(wav)` com o mesmo retorno (endpoint compatível com a OpenAI, `multipart` com `file` e `model`, `language=pt`) e escolher por variável de ambiente. Não comparei qualidade com sotaque regional: **precisa de teste com gravações reais**, o que não foi feito.

## 6. O que NÃO consegui abrir ou instalar

- Página de preços do Azure e do Google Cloud: valores não lidos (tabela vazia ou cortada); lista de vozes pt-BR do Google e do Azure Learn: cortadas.
- Ajuda da ElevenLabs sobre uso comercial: 403. Página da Apple sobre vozes: texto sem o conteúdo.
- Preço da Groq por hora de áudio: não encontrado.
- Fish Speech, F5-TTS, Sherpa-ONNX: não pesquisados.
- Nada de nuvem foi testado (sem conta, como combinado).
- Os WAVs não foram ouvidos por mim.

## 7. Vozes femininas (pesquisa de 2026-11-14, a pedido do usuário)

Mesma regra de confiança de antes: páginas abertas com WebFetch/WebSearch (**resumo** feito por modelo pequeno, salvo onde diz "tabela lida"); **não ouvi nenhum áudio**; a qualidade abaixo é o que a fonte diz, não opinião minha. Onde a página não trouxe o dado: "não li".

### 7.1 Achados principais

- **Piper pt-BR oficial (`rhasspy/piper-voices`, pasta `pt/pt_BR`)**: só 4 vozes: cadu, edresson, faber, jeff (listagem lida em https://huggingface.co/api/models/rhasspy/piper-voices/tree/main/pt/pt_BR). **Nenhuma é anunciada como feminina** (os cartões não dizem o gênero; os nomes e o corpus são masculinos, não confirmei por escrito). Logo **não existe Piper feminino oficial em pt-BR**.
- **Piper da comunidade com voz feminina pt-BR: `Phoonnx/pipertts_pt-BR_dii`** (https://huggingface.co/Phoonnx/pipertts_pt-BR_dii, resumo): "female voice", VITS 22,05 kHz, treinada em dataset **sintético** e ajustada a partir da voz pt-PT "dii". **Licença CC BY-NC-ND 4.0 (não comercial, sem derivados)**. Por isso **não baixei nem testei**. Espelho ONNX provável: `csukuangfj/vits-piper-pt_BR-dii-high` (apareceu na busca https://huggingface.co/api/models?search=piper&filter=pt; **não abri**, licença desconhecida). Se o uso do Sulco for estritamente não comercial (demonstração do desafio), vale testar; senão, pedir autorização à TigreGotico Lda.
- **Kokoro-82M** (VOICES.md, resumo, https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md): pt-BR tem 3 vozes, **só `pf_dora` é feminina** (pm_alex e pm_santa são masculinas). Licença dos pesos: Apache-2.0. A página não dá nota de qualidade nem horas de treino para as vozes pt-BR. Confirmei no arquivo `voices-v1.0.bin` local: o prefixo `p` tem exatamente `pf_dora`, `pm_alex`, `pm_santa`.
- **Nuvem tem muitas femininas pt-BR** (listas oficiais lidas, ver 7.3).
- Modelos abertos novos: quase todos com licença **não comercial** ou sem CPU viável aqui (7.4).

### 7.2 Teste local (CPU, 8 núcleos, 7 GB, máquina ocupada, Kokoro int8)

Frase idêntica à do teste anterior. Tempos de geração do pior caso. Arquivos em `/tmp/claude-1000/voz/amostras/femininas/`:

| WAV | Voz | Velocidade | Geração | Duração do áudio | Observação |
|---|---|---|---|---|---|
| `kokoro_pf_dora_v1.0.wav` | pf_dora (pt-BR nativa) | 1,0 | 8,0 s | 11,6 s | a única feminina pt-BR do Kokoro |
| `kokoro_pf_dora_v0.95.wav` | pf_dora | 0,95 | 9,1 s | 11,9 s | variante pedida |
| `kokoro_ef_dora_v0.95.wav` | ef_dora (espanhola) | 0,95 | 7,6 s | 11,8 s | EXPERIMENTO: voz de outro idioma lendo pt-BR; provável sotaque |
| `kokoro_af_heart_v0.95.wav` | af_heart (inglesa EUA) | 0,95 | 9,0 s | 14,1 s | EXPERIMENTO: sotaque americano provável |
| `kokoro_if_sara_v0.95.wav` | if_sara (italiana) | 0,95 | 8,2 s | 11,4 s | EXPERIMENTO: sotaque italiano provável |

As três de outros idiomas são só curiosidade: **não servem para produção sem aprovação de ouvido** (o fonemizador é pt-BR, mas o timbre/prosódia vem do outro idioma). Todas as WAV: 24 kHz, mono.

Não rodaram aqui (motivo): Piper feminina oficial (não existe); Piper `dii` (licença NC-ND); Chatterbox multilingual, Qwen3-TTS, XTTS-v2, Fish/OpenAudio, F5-TTS pt-br (precisam de PyTorch ~1 GB + pesos de 1 a 2 GB; `/tmp` é tmpfs com ~1,9 GB livres, sem GPU, e vários são NC, ver 7.4); Gradium phonon (repositório com login; não uso contas). Nada de nuvem foi testado.

### 7.3 Tabela das opções femininas

Custos são os da última pesquisa (resumo) ou "não li". Latência: nenhuma medida por mim, salvo as locais.

| Opção | Vozes femininas pt-BR (fonte) | Qualidade relatada | Custo / grátis | Licença / uso comercial | Privacidade | Peso / latência |
|---|---|---|---|---|---|---|
| **Kokoro pf_dora** | pf_dora (VOICES.md, resumo) | sem nota na página; **ouvir** | grátis | pesos Apache-2.0; espeak-ng GPL | local | 92 MB + 28 MB; ~8 a 9 s para ~12 s de áudio (quase tempo real) |
| **Piper pt-BR oficial** | nenhuma feminina | n/a | grátis | n/a | local | n/a |
| **Piper `Phoonnx/pipertts_pt-BR_dii`** | Dii (feminina; resumo) | não declarada; dataset sintético | grátis | **CC BY-NC-ND 4.0: não comercial, sem derivados** | local | ~60 MB estimado (não li); rápido como Piper |
| **Azure AI Speech** | Tabela oficial lida (https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts, resumo mas com linhas citadas): **HD** `pt-BR-Thalita:DragonHDLatestNeural`; **Multilingual** `pt-BR-ThalitaMultilingualNeural`; **MAI-Voice-2** `pt-BR-Luana:MAI-Voice-2` e `...-Flash` (feminina; a lista só tem Luana como feminina MAI); **Standard** Francisca, Thalita, Brenda, Elza, Giovanna, Leila, Manuela, Yara (e Leticia, infantil) | HD/MAI são as "mais humanas" da Microsoft pela própria documentação; sem nota pt-BR medida | F0 0,5 M caracteres/mês neural (resumo anterior); preço HD: não li | serviço pago | texto vai à Microsoft | 0 MB; latência não medida (Flash é a variante de baixa latência) |
| **Google Cloud TTS** | Lista oficial lida (https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types, resumo, offset 170000): **pt-BR é suportado em Chirp 3 HD**; femininas: Achernar, Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux, Kore, Laomedeia, Leda, Pulcherrima, Sulafat, Vindemiatrix, Zephyr; Neural2-A e C; WaveNet A, C, D; Standard A, C, D | Chirp 3 HD é a linha "Premium" da lista; sem nota medida | **Preço: não li** (a página oficial veio só com o título nas 3 tentativas). Terceiros dizem ~1 M caracteres grátis em Neural2/Chirp e US$ 16 / 30 por 1 M: **não confiar** | pago | vai ao Google | 0 MB; Chirp 3 HD sem SSML nem controle de velocidade (resumo anterior) |
| **Amazon Polly** | Camila (generative, neural, standard), Vitória (neural, standard) (https://aws.amazon.com/polly/features/, resumo). A lista anterior citava Carolina e Leo (generative): esta página **não** as lista; divergência não resolvida | generative é a mais natural da Polly pela própria descrição (não li métrica) | preços da pesquisa anterior (resumo): neural US$ 16/1 M, generative US$ 30/1 M; grátis só 12 meses | pago | vai à Amazon | latência não medida |
| **ElevenLabs** | não consegui ver a biblioteca de vozes pt-BR (página dinâmica); **não li** nomes | citada como muito natural; não verifiquei | https://elevenlabs.io/pricing (resumo): Free US$ 0 = **10 000 créditos/mês**; **licença comercial só a partir do plano Starter**; a página não diz se o Free tem API | Free: sem uso comercial | vai à ElevenLabs | n/a |
| **OpenAI TTS** | vozes: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar (13; a própria página também diz "11"); gênero **não declarado** na página; português suportado (otimizadas para inglês) (https://developers.openai.com/api/docs/guides/text-to-speech, resumo) | recomenda marin/cedar para melhor qualidade | preços da pesquisa anterior (resumo) | pago; **exige avisar o usuário que a voz é de IA** | vai à OpenAI | n/a |
| **Edge/edge-tts** | Francisca e Thalita são as mesmas vozes neurais da Azure | n/a | grátis mas **não oficial** | risco de termos | vai à Microsoft | evitar em produto |
| **MMS-TTS por (Meta)** | gênero não informado | sem métricas (VITS 36,3 M parâmetros) | grátis | **CC-BY-NC 4.0** (https://huggingface.co/facebook/mms-tts-por, resumo) | local | pequeno; não comercial |
| **Coqui XTTS-v2** | clona voz (qualquer gênero por amostra) | pt está entre as 17 línguas | grátis | Coqui Public Model License (CPML); página não diz se comercial é permitido: **não confirmado** (https://huggingface.co/coqui/XTTS-v2, resumo) | local | GPU nos exemplos; CPU não confirmado |

### 7.4 Modelos abertos recentes

| Modelo | O que a fonte diz (resumo) | Decisão |
|---|---|---|
| **F5-TTS pt-br (firstpixel)** https://huggingface.co/firstpixel/F5-TTS-pt-br | metadados: cc-by-nc-4.0, base SWivid/F5-TTS; "teste preliminar" só português; "330+ h" vem de terceiro | não comercial; clona voz de uma referência; não testei |
| **Gradium phonon-40m-pt** https://huggingface.co/gradium/phonon-40m-pt | 40 M parâmetros, GGUF q8 de 74,6 MB, roda em CPU/celular/navegador; ~100 vozes (cita "Isadora" pt-br, gênero não dito); Elo 2144 e WER 1,1% (números do **fabricante**); **CC BY-NC 4.0**; arquivos exigem aceitar condições e login | promissor tecnicamente (pequeno, pt nativo), mas NC e com login: não testei; **pedir licença comercial à Gradium** se gostarem |
| **Chatterbox multilingual (Resemble AI)** https://huggingface.co/ResembleAI/chatterbox | português entre 23 línguas; **MIT**; ~0,5 B parâmetros; exemplos em CUDA; **marca d'água PerTh em todo áudio**; clona por áudio de referência | licença boa, mas pesado para 7 GB sem GPU; não testei. Existe fine-tune pt-BR (https://huggingface.co/gorack/Chatterbox-TTS-Portuguese, só apareceu na busca; **não abri**) |
| **Qwen3-TTS 0.6B CustomVoice** https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice | português suportado; **Apache-2.0**; ~0,9 B parâmetros; exemplos em CUDA; falantes pré-definidos femininos são chinesa (Vivian, Serena), japonesa (Ono_Anna) e coreana (Sohee): **nenhum nativo de pt** | sotaque estrangeiro provável; não testei |
| **Fish/OpenAudio S1-mini** https://huggingface.co/fishaudio/openaudio-s1-mini | pt entre 13 línguas; 0,5 B; **CC-BY-NC-SA-4.0**; repositório com acesso condicionado | não comercial; não testei |
| Orpheus, Kyutai, Sesame CSM, Kani, VITS "Cetacea" | **não pesquisei a fundo** (sem tempo) | lacuna |
| Microsoft MAI-Voice | existe no Azure como "MAI-Voice-2" (tabela acima); `Luana` é a feminina pt-BR | ver Azure |

### 7.5 Ranking sugerido (para o Sulco)

Critério: feminina, pt-BR, licença que permita uso, custo e privacidade. **Sem ouvir, o ranking de naturalidade é hipótese**; o passo 0 é uma pessoa ouvir os WAV.

0. **Ouvir `kokoro_pf_dora_v1.0.wav` e `kokoro_pf_dora_v0.95.wav`** (já gerados) e, se quiser comparar nuvem, ouvir as demos oficiais de Azure (Thalita HD / Luana) e Google (Chirp 3 HD pt-BR) no site de cada uma (não abri nem usei; exigem página própria).
1. **Kokoro pf_dora, local**: a única feminina pt-BR com licença permissiva que roda na máquina; sem custo; texto não sai do servidor. Contras: quase tempo real (8 a 9 s para ~12 s) e naturalidade desconhecida.
2. **Azure `pt-BR-Thalita:DragonHDLatestNeural` ou `pt-BR-Luana:MAI-Voice-2-Flash`** se a pf_dora não agradar e for aceitável enviar o texto à Microsoft: ambas aparecem na lista oficial como Neural HD. Conferir preço na página de Azure antes (não li).
3. **Google Chirp 3 HD (Aoede, Kore, Leda, Zephyr...)**: pt-BR confirmado na lista oficial; conferir preço (não li) e que não há controle de velocidade.
4. **Polly Camila (generative)**: confirmada pt-BR feminina; US$ 30/1 M (resumo anterior).
5. **Piper `dii`** só se o uso for não comercial (NC-ND) e alguém aprovar o timbre.
6. Evitar: edge-tts; MMS, F5-TTS pt-br, OpenAudio, phonon (NC) sem licença própria.

### 7.6 Passos de integração ao `/voz/falar` (voz feminina)

Segue o desenho da seção 4 (`MOTORES_TTS`), só trocando o motor:

1. Dependências no venv do projeto: `pip install kokoro-onnx` (0.4.7 testada). Baixar `kokoro-v1.0.int8.onnx` e `voices-v1.0.bin` para `data/modelos_voz/` (não versionar) e conferir o sha256 da tabela da seção 2. Instalar `espeak-ng` no sistema/Docker (o fonemizador é GPL: registrar).
2. Função com a mesma interface de `_tts_deepseek`, carregando o modelo uma vez:

```python
_KOKORO = None

def _tts_kokoro(texto: str, voz: str = "pf_dora", velocidade: float = 0.95) -> bytes:  # pragma: no cover
    import io, wave
    import numpy as np
    from kokoro_onnx import Kokoro
    global _KOKORO
    if _KOKORO is None:
        _KOKORO = Kokoro(str(RAIZ / "data/modelos_voz/kokoro-v1.0.int8.onnx"),
                         str(RAIZ / "data/modelos_voz/voices-v1.0.bin"))
    a, sr = _KOKORO.create(texto, voice=voz, speed=velocidade, lang="pt-br")
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    return buf.getvalue()
```

3. `MOTORES_TTS = {"deepseek": _tts_deepseek, "kokoro": _tts_kokoro}`; no `falar`, validar `motor` (400 se fora da lista); não somar custo para Kokoro, mas manter o limite de caracteres (CPU: ~0,7 s de processamento por segundo de áudio nesta máquina). Aceitar só vozes da lista fixa (`pf_dora`) para evitar caminho livre de arquivo.
4. Se escolher nuvem (Azure/Google/Polly): criar `_tts_azure` etc. com a mesma assinatura, chave só por variável de ambiente, aviso de privacidade na tela e contador de caracteres para o teto de gasto. Só depois de o usuário criar conta e aprovar o preço.
5. Testes: `monkeypatch` do motor como já é feito; teste de `motor`/`voz` inválidos (400).
6. Fazer só depois de alguém ouvir e aprovar.

### 7.7 O que não abri ou não consegui

- Preço oficial do Google TTS (3 tentativas: página só com título), preço do Azure HD/MAI, biblioteca de vozes da ElevenLabs, página do Piper `csukuangfj/...-dii-high`, `gorack/Chatterbox-TTS-Portuguese`, Orpheus/Kyutai/Sesame/Kani/Cetacea.
- Nenhum áudio foi ouvido; nenhuma nuvem foi usada; nenhum modelo com licença NC foi baixado.
