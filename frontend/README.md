# Front-end Maíra

Front-end React/Vite para a conversa consultiva do SULCO. A interface usa `POST /conversa` e `GET /municipios`/`GET /saude` da API existente. A voz usa as APIs nativas de reconhecimento e síntese do navegador; não chama nenhuma rota `/voz/*` e não pede PIN.

## Conversa por voz

- Quando o navegador oferece `SpeechRecognition`/`webkitSpeechRecognition`, aparece o botão grande **Falar**. A escuta usa português do Brasil e mostra a transcrição enquanto a pessoa fala.
- A fala é enviada após 3,5 segundos de silêncio. Se o navegador encerrar a escuta durante uma pausa, a escuta reabre e junta o texto sem repetir trechos sobrepostos. **Terminei** envia imediatamente.
- A resposta pode ser lida pela voz do celular, em trechos curtos. Tocar no controle durante a leitura interrompe. O seletor permite conversa contínua (ouve novamente após a resposta) ou um toque por vez. A Maíra não inicia áudio nem cumprimenta primeiro.
- Sem reconhecimento de voz, o botão e as opções de modo de voz ficam ocultos; a conversa por texto continua disponível.
- A espera mostra etapas na tela e, na conversa por voz, diz “Só um instante, estou olhando os dados.” após três segundos. A chamada tem limite de 100 segundos e exibe uma mensagem simples em caso de falha ou demora.
- O campo de texto permanece disponível durante a espera. Os chips continuam opcionais; o estado devolvido pela API é enviado no turno seguinte. Mensagens e estado vivem somente na memória da aba.

O build de produção é servido sob `/app`; os pedidos seguem usando caminhos absolutos `/conversa`, `/municipios` e `/saude`, e o Vite publica os arquivos compilados em `dist/` com assets em `/assets`.

O build TypeScript/Vite foi conferido com `npm run build`. O microfone, o reconhecimento e as vozes reais do aparelho não foram testados em um celular; o comportamento depende do suporte e das permissões do navegador.

## Desenvolvimento local

Em um terminal, inicie a API:

```sh
.venv/bin/uvicorn src.api.main:app --port 8000
```

Em outro, neste diretório:

```sh
npm install
npm run dev
```

O Vite encaminha as chamadas da API para `http://127.0.0.1:8000`. Se a API estiver em outro endereço, defina `SULCO_API_PROXY` antes de iniciar o Vite.

## Build e publicação

```sh
npm run build
```

O build fica em `dist/`. Para produção, sirva o front e encaminhe `/conversa`, `/municipios` e `/saude` para o mesmo host da API (ou use um proxy reverso no mesmo domínio). A API não libera CORS para uma origem separada. O estado da conversa e as mensagens ficam apenas na memória da aba; não há histórico em `localStorage`.
