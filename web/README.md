# Sulco Web

Front-end React + TypeScript organizado em **MVVM**. Fica separado do `frontend/` (chat da Maíra), que continua como está.

## Stack

| Para quê | Lib |
|---|---|
| Build / dev | Vite 8, TypeScript 6 |
| Estilo | Tailwind CSS 4 (`@tailwindcss/vite`), `clsx` + `tailwind-merge` (`cn()`) |
| Rotas | TanStack Router (rotas por arquivo em `src/routes`, code-splitting automático) |
| Dados do servidor | TanStack Query + `zod` (valida as respostas da API) |
| Ícones | Phosphor (`@phosphor-icons/react`) |
| `<head>` / SEO | `react-helmet-async` (componente `Seo`) |
| 3D | `three`, `@react-three/fiber`, `@react-three/drei` (carregados só nas telas 3D) |
| Qualidade | ESLint 10 (+ react-hooks / React Compiler rules), Prettier (+ ordem de classes Tailwind), Vitest + Testing Library |

## Comandos

```sh
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc + vite build → dist/
npm run lint
npm run test
npm run format
```

Em dev, chamadas para `/api/*` vão para `SULCO_API_PROXY` (padrão `http://127.0.0.1:8000`) **sem** o prefixo `/api`. Ex.: `/api/municipios` → `http://127.0.0.1:8000/municipios`. Suba a API com:

```sh
.venv/bin/uvicorn src.api.main:app --port 8000
```

Em produção, o prefixo vem de `VITE_API_BASE_URL` (padrão `/api`); o proxy reverso deve fazer a mesma reescrita.

## Estrutura

```
src/
  main.tsx                    # monta Providers + Router
  app/
    router.ts                 # createRouter + tipagem global
    providers/                # QueryClient, Helmet, IconContext do Phosphor
    styles/index.css          # Tailwind + tokens do tema (@theme)
  routes/                     # SÓ roteamento: path, search params, loader → View
    __root.tsx
    index.tsx
    municipios.tsx
  routeTree.gen.ts            # gerado pelo plugin do router (não editar)
  features/
    <feature>/
      models/                 # M  — schemas zod, tipos e regras puras de domínio
      services/               #      acesso à API (único lugar que conhece URLs)
      viewmodels/             # VM — hooks useXViewModel: estado + comandos para a View
      views/                  # V  — componentes de tela, sem fetch nem regra
      components/             #      peças visuais da feature (ex.: cenas 3D)
  shared/
    api/httpClient.ts         # fetch + timeout + validação zod + ApiError
    components/               # ui/, layout/, seo/
    lib/                      # utilitários puros (cn, normalização de texto)
  test/setup.ts
```

### Regras do MVVM aqui

- **Route** → declara caminho, valida search params com zod e pré-carrega dados (`loader`). Renderiza uma View.
- **View** → chama **um** ViewModel e desenha. Não importa `services/` (o ESLint bloqueia).
- **ViewModel** → hook que junta Query, estado da URL e estado local; devolve `{ estado..., comandos... }`. Regras puras ficam em funções separadas (ex.: `filtrarMunicipios`) para testar sem React.
- **Model** → schema zod = contrato com a API. Se o back-end mudar o formato, o erro aparece no `httpClient`, não na tela.
- **Service** → funções finas sobre `http.get/post`.

### Criando uma feature nova

1. `features/x/models/x.model.ts` — schema zod + tipo.
2. `features/x/services/x.service.ts` — `http.get("/rota", schema)`.
3. `features/x/viewmodels/useXViewModel.ts` — `useQuery`/`useMutation` + estado e comandos.
4. `features/x/views/XView.tsx` — usa o ViewModel; `<Seo title="..." />` no topo.
5. `routes/x.tsx` — `createFileRoute("/x")({ component: XView })`. O `routeTree.gen.ts` se atualiza sozinho com o `npm run dev`.

## Exemplos incluídos

- `/` — status da API (`GET /saude`, só o campo `status`) e uma cena 3D de "sulcos" animada.
- `/municipios` — lista de `GET /municipios` com busca na URL (`?q=`), sem acento/caixa, e mapa 3D dos pontos por lat/lon (clique seleciona). `ibge: null` aparece como "sem dado".

As regras do produto em `docs/32_FRONTEND_HANDOFF.md` (seção 4) valem aqui também: texto da API só como texto, nada de número inventado, nenhum caminho/chave em tela.

## Docker

Build e execução da imagem de produção em contêiner Nginx:

```sh
# A partir da pasta web:
docker build -t sulco-web .
docker run -d -p 3000:80 sulco-web

# Ou a partir da raiz do repositório:
docker compose -f docker-compose.frontend.yml up --build -d
```
Acesse em `http://localhost:3000`. O endpoint `/healthz` responde `healthy`.
