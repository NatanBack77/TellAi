# GitHub Actions & GitOps CI/CD Templates for SULCO

Modelos prontos de esteiras de automação e integração contínua para o repositório SULCO.

---

## 1. Pipeline Completo de CI (.github/workflows/ci.yml)

```yaml
name: SULCO CI Pipeline

on:
  push:
    branches: [ main, feat/* ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Install uv and Python
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
          enable-cache: true

      - name: Create venv and install dependencies
        run: |
          uv venv .venv --python 3.14
          source .venv/bin/activate
          uv pip install -r requirements-runtime.txt pytest httpx

      - name: Run Fast Unit Tests
        run: |
          source .venv/bin/activate
          python -m pytest tests/test_consorcio.py tests/test_features.py tests/test_culturas.py -q

  docker-build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker Image (Dry Run Check)
        uses: docker/build-push-action@v5
        with:
          context: .
          target: final
          push: false
          tags: sulco:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 2. Configuração do Frontend na Vercel (vercel.json)

Para implantar o frontend da Maíra isoladamente na Vercel:

```json
{
  "framework": "vite",
  "rootDirectory": "frontend",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```
Injetar a variável de ambiente:
- `VITE_API_URL`: URL pública da sua API FastAPI (ex: `https://api.sulco.agro`).
