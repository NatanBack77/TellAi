"""App ASGI de TESTE com a conversa por voz: a API normal (src.api.main) + as rotas /voz.

    .venv/bin/uvicorn src.api.voz_app:app --host 0.0.0.0 --port 8443 --ssl-keyfile <chave.pem> --ssl-certfile <cert.pem>

Existe separado de `main.py` para não mexer na API de produção enquanto a voz é testada. O microfone do celular só funciona em HTTPS."""
from src.api.main import app  # noqa: F401  (a API completa: /chat, /municipios, /saude ...)
from src.api import voz

app.include_router(voz.router)


def aquecer():   # pragma: no cover - modelo local
    import threading
    def _a():
        try:
            voz._tts_kokoro("Oi.")          # carrega a voz da Dora
        except Exception:
            pass
        try:                                  # pré-gera as frases fixas da conversa (saudação, "ok", esperas): saem sem esperar
            from src.llm import conversa as _c
            for t in (*(_c.texto_saudacao(k) for k in ('oi', *_c.SAUDACOES)), _c.TEXTO_OK_LIVRE, _c.TEXTO_OK_FOCO, _c.TEXTO_AGRADECE,
                      "Só um instante, estou olhando os dados.", "Ainda estou conferindo, já te respondo.", "O resto está escrito na tela."):
                voz._tts_kokoro(voz.cortar_para_fala(t))
        except Exception:
            pass
        try:                                  # carrega a busca (RAG), os dados do local e o motor: a 1ª pergunta não paga ~7 s
            from src.llm import conversa as _c
            _c.conversar("o que é veranico?", None, "quixada_ce", None, None, modo="offline", permitir_stub=True)
            _c.conversar("o que dá para plantar aqui?", None, "quixada_ce", None, None, modo="offline", permitir_stub=True)
        except Exception:
            pass
    threading.Thread(target=_a, daemon=True).start()


app.router.on_startup.append(aquecer)   # sem o decorator on_event (obsoleto): carrega a Dora ao subir


# ---------------------------------------------------------------- front-end da Maíra (React/Vite, pasta frontend/dist), servido no MESMO endereço
# (mesma origem: não precisa de CORS). Só neste app de teste. Gere com:  cd frontend && npm run build
from pathlib import Path as _Path  # noqa: E402

from fastapi.responses import FileResponse as _FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: E402

_DIST = _Path(__file__).resolve().parents[2] / "frontend" / "dist"
_CSP_FRONT = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
              "connect-src 'self'; media-src 'self' blob: data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

if (_DIST / "index.html").exists():
    app.mount("/assets", _StaticFiles(directory=str(_DIST / "assets")), name="front_assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/", include_in_schema=False)
    def front():
        return _FileResponse(_DIST / "index.html", headers={"Content-Security-Policy": _CSP_FRONT, "Cache-Control": "no-store"})

    @app.get("/maira.jpeg", include_in_schema=False)
    def front_foto():
        return _FileResponse(_DIST / "maira.jpeg")
