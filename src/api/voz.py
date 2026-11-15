"""Conversa por VOZ no navegador do celular (ferramenta de teste): falar -> DeepSeek ASR -> chat do Sulco -> DeepSeek TTS -> áudio.

Rotas (todas protegidas por PIN no cabeçalho `X-Voz-Pin`, definido em SULCO_VOZ_PIN no .env):
  GET  /voz                página da conversa (HTML puro, feita para celular)
  POST /voz/transcrever    corpo = WAV 16 bits (mono/estéreo), até 8 MiB e 120 s  ->  {texto, duracao_ms}
  POST /voz/falar          JSON {texto} (até 450 caracteres, cortado em fim de frase)  ->  audio/wav
  GET  /voz/estado         gasto do dia e tetos (nunca a chave nem o PIN)

Fatos verificados na documentação oficial (https://api-docs.deepseek.com/guides/asr e /guides/tts, 2026-11-14):
- ASR: POST /v1/tools/asr, multipart (campo `file`), WAV PCM 16 bits ou Ogg Opus; ≤ 8 MiB e ≤ 120 s; áudio inteiro, SEM streaming;
  português na lista (`pt`), idioma detectado; US$ 0,116/hora de áudio de lista.
- TTS: POST /v1/tools/tts, JSON {text, voice_id, format}; PORTUGUÊS NÃO ESTÁ NA LISTA de idiomas (funciona na prática, sem garantia de
  qualidade); US$ 0,45 por 10.000 caracteres de lista.

Trava de gasto própria (voz custa mais que texto): SULCO_VOZ_MAX_SEG_DIA (padrão 900 s de áudio) e SULCO_VOZ_MAX_CHARS_DIA (padrão 4000
caracteres falados). Contadores em data/processed/llm_cache/gasto_voz.json (ignorado pelo git), sem áudio, sem texto, sem chave.
Privacidade: o áudio e o texto falado vão à DeepSeek; a página avisa. Nada é gravado em disco por este módulo."""
from __future__ import annotations

import datetime
import hmac
import io
import json
import os
import re
import threading
import time
import uuid
import wave
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

RAIZ = Path(__file__).resolve().parents[2]
URL_ASR = "https://api.deepseek.com/v1/tools/asr"
URL_TTS = "https://api.deepseek.com/v1/tools/tts"
MAX_BYTES = 8 * 1024 * 1024
MAX_SEG = 120.0
MAX_CHARS_FALA = 450
PRECO_ASR_HORA = 0.116      # US$/hora de áudio (lista)
PRECO_TTS_10K = 0.45        # US$ por 10.000 caracteres (lista)

router = APIRouter(prefix="/voz", tags=["voz"])


# ---------------------------------------------------------------- configuração e gasto
def _pin() -> str:
    return (os.environ.get("SULCO_VOZ_PIN") or "").strip()


def _teto_seg() -> float:
    try:
        return float(os.environ.get("SULCO_VOZ_MAX_SEG_DIA", "900"))
    except ValueError:
        return 900.0


def _teto_chars() -> int:
    try:
        return int(os.environ.get("SULCO_VOZ_MAX_CHARS_DIA", "4000"))
    except ValueError:
        return 4000


def _arq_gasto() -> Path:
    return Path(os.environ.get("SULCO_GASTO_VOZ_ARQ") or RAIZ / "data" / "processed" / "llm_cache" / "gasto_voz.json")


def _ler_gasto() -> dict:
    hoje = datetime.date.today().isoformat()
    try:
        d = json.loads(_arq_gasto().read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("data") == hoje:
            return d
    except (OSError, ValueError):
        pass
    return {"data": hoje, "seg_audio_dia": 0.0, "chars_fala_dia": 0, "chamadas_asr_dia": 0, "chamadas_tts_dia": 0}


def _gravar_gasto(d: dict) -> None:
    try:
        a = _arq_gasto()
        a.parent.mkdir(parents=True, exist_ok=True)
        a.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# Bloqueio contra adivinhação do PIN (docs/30_SEGURANCA_IA.md, ameaça A-05): falhas por IP e globais numa janela; estourou => 429.
MAX_FALHAS_IP, JANELA_FALHAS_S = 8, 300.0
MAX_FALHAS_GLOBAL, JANELA_GLOBAL_S = 60, 900.0
_FALHAS: dict[str, list[float]] = {}
_FALHAS_GLOBAL: list[float] = []
_TRAVA_PIN = threading.Lock()


def _ip(request) -> str:
    return (request.client.host if request is not None and getattr(request, "client", None) else None) or "desconhecido"


def _exigir_pin(pin: str | None, request=None) -> None:
    esperado = _pin()
    if not esperado:
        raise HTTPException(503, "Voz desligada: defina SULCO_VOZ_PIN no .env (qualquer número de 4 a 8 dígitos) e reinicie.")
    ip, agora = _ip(request), time.monotonic()
    with _TRAVA_PIN:
        fs = [t for t in _FALHAS.get(ip, []) if agora - t < JANELA_FALHAS_S]
        _FALHAS_GLOBAL[:] = [t for t in _FALHAS_GLOBAL if agora - t < JANELA_GLOBAL_S]
        if len(fs) >= MAX_FALHAS_IP or len(_FALHAS_GLOBAL) >= MAX_FALHAS_GLOBAL:
            raise HTTPException(429, "Muitas tentativas de PIN. Espere alguns minutos.", headers={"Retry-After": str(int(JANELA_FALHAS_S))})
        if not pin or not hmac.compare_digest(pin.encode(), esperado.encode()):
            fs.append(agora)
            _FALHAS_GLOBAL.append(agora)
            if len(_FALHAS) >= 5000:
                _FALHAS.pop(next(iter(_FALHAS)))
            _FALHAS[ip] = fs
            raise HTTPException(401, "PIN incorreto.")
        _FALHAS.pop(ip, None)


async def _ler_corpo(request, limite: int) -> bytes:
    """Lê o corpo SEM confiar no Content-Length e para ao passar do limite (não carrega upload gigante na memória)."""
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > limite:
        raise HTTPException(413, "Corpo grande demais.")
    partes, total = [], 0
    async for pedaco in request.stream():
        total += len(pedaco)
        if total > limite:
            raise HTTPException(413, "Corpo grande demais.")
        partes.append(pedaco)
    return b"".join(partes)


def _chave() -> str:
    from src.llm.ambiente import carregar_env
    from src.llm.provedores import ler_chave_env
    carregar_env()
    k = ler_chave_env()
    if not k:
        raise HTTPException(503, "DEEPSEEK_API_KEY não configurada no .env.")
    return k


# ---------------------------------------------------------------- áudio
def validar_wav(dados: bytes) -> float:
    """Confere cabeçalho WAV PCM 16 bits e devolve a duração em segundos. Levanta HTTPException 400/413."""
    if len(dados) > MAX_BYTES:
        raise HTTPException(413, "Áudio maior que 8 MiB.")
    try:
        with wave.open(io.BytesIO(dados), "rb") as w:
            ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except (wave.Error, EOFError):
        raise HTTPException(400, "Envie um arquivo WAV PCM de 16 bits.")
    if sw != 2 or ch not in (1, 2) or not 8000 <= fr <= 48000:
        raise HTTPException(400, "WAV precisa ser PCM 16 bits, mono ou estéreo, de 8000 a 48000 Hz.")
    dur = n / float(fr)
    if dur <= 0.3:
        raise HTTPException(400, "Áudio muito curto.")
    if dur > MAX_SEG:
        raise HTTPException(413, "Áudio maior que 120 segundos.")
    return dur


def _multipart(campo: str, nome: str, conteudo: bytes, tipo: str) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    cab = f'--{b}\r\nContent-Disposition: form-data; name="{campo}"; filename="{nome}"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
    return cab + conteudo + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def _asr_deepseek(wav: bytes) -> dict:   # pragma: no cover - rede (os testes substituem esta função)
    import urllib.error
    import urllib.request
    corpo, tipo = _multipart("file", "fala.wav", wav, "audio/wav")
    req = urllib.request.Request(URL_ASR, data=corpo, method="POST",
                                 headers={"Authorization": "Bearer " + _chave(), "Content-Type": tipo})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPException(502 if e.code >= 500 else e.code, f"A DeepSeek recusou o áudio (HTTP {e.code}).")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Falha ao falar com a DeepSeek ({type(e).__name__}).")


def _tts_deepseek(texto: str, voz: str = "stella") -> bytes:   # pragma: no cover - rede (os testes substituem esta função)
    import urllib.error
    import urllib.request
    req = urllib.request.Request(URL_TTS, data=json.dumps({"text": texto, "voice_id": voz, "format": "wav"}).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + _chave(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise HTTPException(502 if e.code >= 500 else e.code, f"A DeepSeek recusou o texto (HTTP {e.code}).")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Falha ao falar com a DeepSeek ({type(e).__name__}).")


# ---------------------------------------------------------------- voz local (Kokoro, pf_dora): grátis, o texto não sai da máquina
VOZES_KOKORO = ("pf_dora",)          # lista fixa: nunca aceitar nome de arquivo livre
_KOKORO = None
_CACHE_FRASE: dict = {}
_TRAVA_KOKORO = threading.Lock()
PAUSA_S = {".": 0.28, "!": 0.28, "?": 0.32, ";": 0.2, ":": 0.2, ",": 0.1}


def _frases_para_fala(texto: str) -> list[tuple[str, str]]:
    """Divide em frases curtas e devolve (frase, pontuação final), para falar frase a frase com pausa entre elas."""
    t = re.sub(r"\s+", " ", texto or "").strip()
    partes = re.findall(r"[^.!?;:]+[.!?;:]?", t)
    saida = []
    for p in partes:
        p = p.strip()
        if not p:
            continue
        # frases muito longas são quebradas na vírgula mais próxima do meio
        while len(p) > 160 and "," in p[40:-40]:
            i = p.find(",", len(p) // 2 - 30) if p.find(",", len(p) // 2 - 30) > 0 else p.find(",", 40)
            saida.append((p[:i + 1].strip(), ","))
            p = p[i + 1:].strip()
        saida.append((p, p[-1] if p[-1] in PAUSA_S else "."))
    return saida


def _tts_kokoro(texto: str, voz: str = "pf_dora", velocidade: float = 1.0) -> bytes:   # pragma: no cover - modelo local (os testes substituem)
    import numpy as np
    from kokoro_onnx import Kokoro
    global _KOKORO
    if voz not in VOZES_KOKORO:
        raise HTTPException(400, "Voz inválida.")
    pasta = RAIZ / "data" / "modelos_voz"
    modelo, vozes = pasta / "kokoro-v1.0.int8.onnx", pasta / "voices-v1.0.bin"
    if not (modelo.exists() and vozes.exists()):
        raise HTTPException(503, "Voz local não instalada (faltam arquivos em data/modelos_voz/). Veja docs/28.")
    with _TRAVA_KOKORO:
        if _KOKORO is None:
            _KOKORO = Kokoro(str(modelo), str(vozes))
        pedacos, sr = [], 24000
        for frase, fim in _frases_para_fala(texto):
            chave = (voz, velocidade, frase)
            if chave not in _CACHE_FRASE:          # frases repetidas (saudação, "ok", esperas) saem na hora
                a, sr = _KOKORO.create(frase, voice=voz, speed=velocidade, lang="pt-br")
                if len(_CACHE_FRASE) >= 400:
                    _CACHE_FRASE.pop(next(iter(_CACHE_FRASE)))
                _CACHE_FRASE[chave] = (np.asarray(a, dtype=np.float32), sr)
            a, sr = _CACHE_FRASE[chave]
            pedacos.append(a)
            pedacos.append(np.zeros(int(sr * PAUSA_S.get(fim, 0.2)), dtype=np.float32))
    pcm = (np.clip(np.concatenate(pedacos), -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


MOTORES_TTS = {"deepseek": "_tts_deepseek", "kokoro": "_tts_kokoro"}   # nomes das funções (resolvidas na chamada, para os testes poderem substituir)
_CACHE_FALA: dict[str, bytes] = {}
FRASES_FIXAS = {"Só um instante, estou olhando os dados.", "Ainda estou conferindo, já te respondo."}   # frases de espera: geradas uma vez e guardadas


def cortar_para_fala(texto: str, limite: int = MAX_CHARS_FALA) -> str:
    """Remove marcadores/markdown e corta em fim de frase para caber no limite (controla o custo da voz)."""
    t = re.sub(r"\[(?:F?\d+)\]", "", texto or "")
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= limite:
        return t
    corte = t[:limite]
    fim = max(corte.rfind(". "), corte.rfind("? "), corte.rfind("! "), corte.rfind("; "))
    return (corte[:fim + 1] if fim > limite * 0.4 else corte.rsplit(" ", 1)[0]).strip()


# ---------------------------------------------------------------- rotas
@router.post("/transcrever")
async def transcrever(request: Request, x_voz_pin: str | None = Header(None)):
    _exigir_pin(x_voz_pin, request)
    dados = await _ler_corpo(request, MAX_BYTES)
    dur = validar_wav(dados)
    g = _ler_gasto()
    if g["seg_audio_dia"] + dur > _teto_seg():
        raise HTTPException(429, f"Limite diário de voz atingido ({int(_teto_seg())} s de áudio). Digite a pergunta ou volte amanhã.")
    r = _asr_deepseek(dados)
    g["seg_audio_dia"] = round(g["seg_audio_dia"] + max(dur, 1.0), 2)
    g["chamadas_asr_dia"] += 1
    _gravar_gasto(g)
    texto = str(r.get("text") or "").strip()
    return {"texto": texto, "duracao_ms": r.get("duration_ms"), "vazio": not texto}


@router.post("/falar")
async def falar(request: Request, x_voz_pin: str | None = Header(None)):
    _exigir_pin(x_voz_pin, request)
    try:
        corpo = json.loads(await _ler_corpo(request, 16 * 1024))
        if not isinstance(corpo, dict):
            raise ValueError("corpo nao e objeto")
        texto = str(corpo.get("texto") or "")
        motor = str(corpo.get("motor") or "deepseek")
    except ValueError:
        raise HTTPException(400, "Envie JSON {\"texto\": \"...\", \"motor\": \"kokoro|deepseek\"}.")
    if motor not in MOTORES_TTS:
        raise HTTPException(400, "Motor de voz inválido (use kokoro ou deepseek).")
    fala = cortar_para_fala(texto)
    if not fala:
        raise HTTPException(400, "Sem texto para falar.")
    cab = {"Cache-Control": "no-store"}
    if motor == "kokoro":
        # local: sem custo e sem teto de gasto; frases de espera ficam guardadas em memória
        if fala in FRASES_FIXAS and fala in _CACHE_FALA:
            return Response(content=_CACHE_FALA[fala], media_type="audio/wav", headers=cab)
        audio = globals()[MOTORES_TTS["kokoro"]](fala)
        if fala in FRASES_FIXAS:
            _CACHE_FALA[fala] = audio
        return Response(content=audio, media_type="audio/wav", headers=cab)
    g = _ler_gasto()
    if g["chars_fala_dia"] + len(fala) > _teto_chars():
        raise HTTPException(429, f"Limite diário de voz falada atingido ({_teto_chars()} caracteres). Use a voz do navegador ou leia o texto.")
    audio = globals()[MOTORES_TTS["deepseek"]](fala)
    g["chars_fala_dia"] += len(fala)
    g["chamadas_tts_dia"] += 1
    _gravar_gasto(g)
    return Response(content=audio, media_type="audio/wav", headers=cab)


@router.get("/estado")
def estado(request: Request, x_voz_pin: str | None = Header(None)):
    _exigir_pin(x_voz_pin, request)
    g = _ler_gasto()
    custo = g["seg_audio_dia"] / 3600 * PRECO_ASR_HORA + g["chars_fala_dia"] / 10000 * PRECO_TTS_10K
    return {"data": g["data"], "seg_audio_dia": g["seg_audio_dia"], "teto_seg_dia": _teto_seg(), "chars_fala_dia": g["chars_fala_dia"],
            "teto_chars_dia": _teto_chars(), "chamadas_asr_dia": g["chamadas_asr_dia"], "chamadas_tts_dia": g["chamadas_tts_dia"],
            "custo_estimado_usd_dia": round(custo, 4), "obs": "custo pelo preço de lista da doc oficial; estimativa, não medição"}


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina():
    from src.api.pagina_voz import renderizar
    from src.app import mvp as M
    return HTMLResponse(renderizar(M.culturas_disponiveis()), headers={"Cache-Control": "no-store"})
