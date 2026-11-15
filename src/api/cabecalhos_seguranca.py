"""Cabeçalhos de segurança HTTP (OWASP LLM05: saída insegura / defesa em profundidade contra XSS). Módulo PURO, sem dependência de `main`.

Como ligar (3 linhas no main.py, depois dos outros middlewares): ver docs/30_SEGURANCA_IA.md, 'PONTOS DE INTEGRAÇÃO'.

    from src.api.cabecalhos_seguranca import aplicar_cabecalhos
    @app.middleware("http")
    async def cabecalhos_seg(request: Request, call_next):
        return aplicar_cabecalhos(await call_next(request), request.url.path)
"""
from __future__ import annotations

BASE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), payment=(), usb=(), microphone=(self)",
}
# JSON da API: nada é carregado a partir dela.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
# Páginas de teste (/voz, /teste): script e estilo inline (HTML puro), áudio gerado no navegador (blob:/data:), nada externo.
CSP_PAGINA = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob: data:; "
              "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
PAGINAS = ("/voz", "/teste")
ISENTAS_CSP = ("/docs", "/redoc", "/openapi.json")     # Swagger carrega scripts de CDN; em produção desligue (SULCO_DOCS=0)


def aplicar_cabecalhos(resposta, caminho: str):
    """Acrescenta os cabeçalhos que ainda não existem na resposta. Devolve a própria resposta."""
    for k, v in BASE.items():
        resposta.headers.setdefault(k, v)
    if not caminho.startswith(ISENTAS_CSP):
        resposta.headers.setdefault("Content-Security-Policy", CSP_PAGINA if caminho.startswith(PAGINAS) else CSP_API)
    if caminho.startswith(("/chat", "/conversa", "/voz", "/calendario")):
        resposta.headers.setdefault("Cache-Control", "no-store")      # resposta personalizada: não fica em cache de proxy/navegador
    return resposta
