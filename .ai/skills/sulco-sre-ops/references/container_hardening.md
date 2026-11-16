# SULCO — Container Hardening & Production Operations Guide

Guia operacional para engenheiros de plataforma e SRE gerenciarem o SULCO em produção.

---

## 1. Dimensionamento de Recursos (Memory Sizing)

| Componente | Memória Mínima | Memória Recomendada | Justificativa |
|---|---|---|---|
| **API FastAPI (`main:app`)** | 2.5 GB | **3.0 GB** | O PyTorch CPU, embeddings E5-small e o modelo preditivo XGBoost consomem ~2.0 GB de RSS em regime aquecido. |
| **Streamlit (`app.py`)** | 1.0 GB | **2.0 GB** | Cache de sessão, GeoJSON do mapa do Ceará e gráficos interativos Altair/PyDeck. |
| **Frontend Maíra (Nginx/Vercel)** | 128 MB | **256 MB** | Servimento de arquivos estáticos compilados (HTML/JS/CSS). |

---

## 2. Padrões de Segurança no Docker Compose

Para garantir contenção máxima de privilégios:

```yaml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
read_only: true
tmpfs:
  - /tmp
user: "10001:10001"
```

### Por que `read_only: true`?
Impede que qualquer ataque de injeção ou falha de biblioteca consiga gravar binários ou alterar o código-fonte em tempo de execução. As únicas áreas graváveis são os volumes dedicados de cache (`sulco_modelos` e `sulco_llm`).

---

## 3. Gestão do Cold Start (Readiness Probes)

A API do SULCO necessita de até **30 a 90 segundos** na inicialização para pré-aquecer os modelos e carregar os Parquets na memória.
- **Docker Compose:**
  ```yaml
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=5).status == 200 else 1)"]
    start_period: 90s
    interval: 30s
    timeout: 10s
    retries: 3
  ```
- **Kubernetes:**
  Configurar `startupProbe` com `failureThreshold: 18` e `periodSeconds: 5` (dando até 90 segundos para prontidão sem reiniciar o Pod).
