# ==============================================================================
# SULCO Web Frontend — Multi-Stage Production Dockerfile
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build & Bundle
# ------------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Instala dependências de cache primeiro
COPY package.json package-lock.json ./
RUN npm ci

# Copia o código-fonte
COPY . .

# Argumento para URL da API em build-time se necessário
ARG SULCO_API_PROXY=http://api:8000
ENV SULCO_API_PROXY=$SULCO_API_PROXY

# Compilação do TypeScript e bundle com Vite
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Nginx Server
# ------------------------------------------------------------------------------
FROM nginx:alpine AS runner

# Remove configuração padrão do Nginx
RUN rm -rf /etc/nginx/conf.d/*

# Copia configuração customizada com suporte a SPA e Proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia artefatos compilados do estágio anterior
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
