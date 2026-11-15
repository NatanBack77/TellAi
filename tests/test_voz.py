"""Conversa por voz (src/api/voz.py): PIN, validação do WAV, tetos de gasto, corte de texto e página. Sem rede: ASR e TTS são trocados por falsos."""
import io
import json
import wave

import pytest
from fastapi.testclient import TestClient

from src.api import voz as V
from src.api import voz_app

c = TestClient(voz_app.app)
PIN = "4321"


def _wav(seg=1.0, taxa=16000, canais=1, largura=2):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(canais); w.setsampwidth(largura); w.setframerate(taxa)
        w.writeframes(b"\x00\x01" * int(taxa * seg) * canais)
    return b.getvalue()


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("SULCO_VOZ_PIN", PIN)
    monkeypatch.setenv("SULCO_GASTO_VOZ_ARQ", str(tmp_path / "gasto_voz.json"))
    monkeypatch.setenv("SULCO_RATE_LIMIT", "0")
    chamadas = {"asr": 0, "tts": []}

    def asr(wav):
        chamadas["asr"] += 1
        return {"text": "quero economizar água", "duration_ms": 1000}

    def tts(texto, voz="stella"):
        chamadas["tts"].append(texto)
        return _wav(0.5, 24000)

    monkeypatch.setattr(V, "_asr_deepseek", asr)
    monkeypatch.setattr(V, "_tts_deepseek", tts)
    return chamadas


H = {"X-Voz-Pin": PIN}


def test_sem_pin_configurado_a_voz_fica_desligada(monkeypatch):
    monkeypatch.delenv("SULCO_VOZ_PIN")
    assert c.post("/voz/transcrever", content=_wav(), headers={"X-Voz-Pin": "x"}).status_code == 503


def test_pin_obrigatorio_e_correto():
    assert c.post("/voz/transcrever", content=_wav()).status_code == 401
    assert c.post("/voz/transcrever", content=_wav(), headers={"X-Voz-Pin": "0000"}).status_code == 401
    assert c.post("/voz/falar", json={"texto": "oi"}, headers={"X-Voz-Pin": "0000"}).status_code == 401
    assert c.get("/voz/estado").status_code == 401


def test_transcrever_devolve_texto_e_conta_o_gasto(ambiente):
    r = c.post("/voz/transcrever", content=_wav(2.0), headers=H)
    assert r.status_code == 200 and r.json()["texto"] == "quero economizar água" and ambiente["asr"] == 1
    e = c.get("/voz/estado", headers=H).json()
    assert e["seg_audio_dia"] >= 2.0 and e["chamadas_asr_dia"] == 1 and e["custo_estimado_usd_dia"] >= 0


@pytest.mark.parametrize("corpo,codigo", [(b"nao e wav", 400), (_wav(0.1), 400), (_wav(130.0, 8000), 413), (_wav(1.0, 4000), 400),
                                           (_wav(1.0, 16000, 1, 1), 400)])
def test_wav_invalido_e_rejeitado_sem_chamar_a_deepseek(corpo, codigo, ambiente):
    assert c.post("/voz/transcrever", content=corpo, headers=H).status_code == codigo
    assert ambiente["asr"] == 0


def test_estereo_e_aceito():
    assert c.post("/voz/transcrever", content=_wav(1.0, 16000, 2), headers=H).status_code == 200


def test_teto_diario_de_audio(monkeypatch, ambiente):
    monkeypatch.setenv("SULCO_VOZ_MAX_SEG_DIA", "3")
    assert c.post("/voz/transcrever", content=_wav(2.0), headers=H).status_code == 200
    r = c.post("/voz/transcrever", content=_wav(2.0), headers=H)
    assert r.status_code == 429 and "Limite diário" in r.json()["detail"] and ambiente["asr"] == 1


def test_falar_devolve_audio_wav_e_corta_o_texto(ambiente):
    longo = ("Esta é uma frase de teste bem comprida para a voz. " * 20).strip()
    r = c.post("/voz/falar", json={"texto": longo}, headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
    assert len(ambiente["tts"][0]) <= V.MAX_CHARS_FALA and ambiente["tts"][0].endswith(".")


def test_falar_remove_marcadores_e_markdown(ambiente):
    c.post("/voz/falar", json={"texto": "O **verde** está bom [F7] e [1]. Converse com o técnico."}, headers=H)
    t = ambiente["tts"][0]
    assert "[" not in t and "*" not in t and "verde" in t


def test_teto_diario_de_caracteres(monkeypatch, ambiente):
    monkeypatch.setenv("SULCO_VOZ_MAX_CHARS_DIA", "30")
    assert c.post("/voz/falar", json={"texto": "Frase curta de teste."}, headers=H).status_code == 200
    r = c.post("/voz/falar", json={"texto": "Outra frase um pouco maior que o resto."}, headers=H)
    assert r.status_code == 429 and len(ambiente["tts"]) == 1


def test_falar_sem_texto_ou_json_ruim():
    assert c.post("/voz/falar", json={"texto": "  "}, headers=H).status_code == 400
    assert c.post("/voz/falar", content=b"{nao json", headers={**H, "Content-Type": "application/json"}).status_code == 400


def test_estado_nao_vaza_chave_nem_pin():
    t = json.dumps(c.get("/voz/estado", headers=H).json())
    assert "sk-" not in t and PIN not in t


def test_pagina_carrega_e_e_segura():
    r = c.get("/voz")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "__CULTURAS__" not in r.text
    assert "innerHTML" not in r.text and "eval(" not in r.text and "document.write" not in r.text
    assert "Assistente automático" in r.text and "técnico" in r.text
    assert "/voz" not in c.get("/openapi.json").json()["paths"]


def test_cortar_para_fala_em_fim_de_frase():
    t = V.cortar_para_fala("Primeira frase curta. " + "palavra " * 100, 60)
    assert t == "Primeira frase curta." or len(t) <= 60


def test_rotas_de_voz_sao_pesadas_no_limite_de_taxa():
    from src.api.limite_taxa import LimiteTaxa
    assert LimiteTaxa.grupo("/voz/transcrever") == "pesado" and LimiteTaxa.grupo("/voz/falar") == "pesado"
    assert LimiteTaxa.grupo("/voz/estado") == "geral"


# ---------------------------------------------------------------- voz local (Kokoro, Dora)
def test_motor_kokoro_nao_gasta_teto_e_guarda_frase_de_espera(monkeypatch, ambiente):
    usos = []
    monkeypatch.setattr(V, "_tts_kokoro", lambda texto, *a, **k: usos.append(texto) or _wav(0.5, 24000))
    V._CACHE_FALA.clear()
    frase = "Só um instante, estou olhando os dados."
    for _ in range(2):
        r = c.post("/voz/falar", json={"texto": frase, "motor": "kokoro"}, headers=H)
        assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert len(usos) == 1                      # a segunda vez veio da memória
    assert ambiente["tts"] == []               # a DeepSeek não foi chamada
    assert c.get("/voz/estado", headers=H).json()["chars_fala_dia"] == 0   # local: sem custo


def test_motor_invalido_e_recusado(ambiente):
    r = c.post("/voz/falar", json={"texto": "oi", "motor": "../../etc/passwd"}, headers=H)
    assert r.status_code == 400


def test_sem_motor_continua_usando_deepseek(ambiente):
    assert c.post("/voz/falar", json={"texto": "Oi, tudo bem?"}, headers=H).status_code == 200
    assert ambiente["tts"] == ["Oi, tudo bem?"]


def test_frases_para_fala_dividem_com_pontuacao():
    assert V._frases_para_fala("Oi! Eu sou o assistente. O que você quer ver?") == [("Oi!", "!"), ("Eu sou o assistente.", "."), ("O que você quer ver?", "?")]


def test_voz_local_so_aceita_voz_da_lista():
    with pytest.raises(Exception):
        V._tts_kokoro("oi", voz="../outra")
