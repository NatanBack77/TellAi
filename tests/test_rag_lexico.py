"""Lexico PT->EN (sem LLM): determinista, sem rede, sem modelos."""
from src.rag.lexico_pt_en import LEXICO, traduzir


def test_traduz_termos_agronomicos():
    en, frac = traduzir("Como a cobertura do solo protege contra chuva e vento?")
    for w in ("cover", "soil", "protects", "rain", "wind"):
        assert w in en.split()
    assert frac >= 0.5


def test_pergunta_fora_do_dominio_nao_traduz():
    en, frac = traduzir("Qual o preço do dólar hoje?")
    assert en == "" and frac == 0.0


def test_determinista_e_vazio():
    assert traduzir("rotação de culturas e pragas") == traduzir("rotação de culturas e pragas")
    assert traduzir("") == ("", 0.0)


def test_lexico_sem_afirmacoes_numericas():
    # o lexico e vocabulario, nao fato: nenhum digito nas traducoes
    assert not any(ch.isdigit() for v in LEXICO.values() for ch in v)
