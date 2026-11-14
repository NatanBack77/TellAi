"""Garante que a suíte não consegue gastar dinheiro: nunca vê a chave real e não abre conexão externa (ver tests/conftest.py)."""
import os
import socket

import pytest

from src.llm import provedores


def test_chave_real_inacessivel():
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-teste-falsa"
    assert os.environ["SULCO_CARREGAR_ENV"] == "0" and os.environ["SULCO_LLM_MODO"] == "template"
    assert provedores.ler_chave_env() == "sk-teste-falsa"


def test_conexao_externa_bloqueada():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="REDE BLOQUEADA"):
            s.connect(("api.deepseek.com", 443))
    finally:
        s.close()          # fecha mesmo se falhar (senão vira ResourceWarning em outro teste)


def test_resolucao_de_nomes_externos_bloqueada():
    with pytest.raises(RuntimeError, match="REDE BLOQUEADA"):
        socket.getaddrinfo("api.deepseek.com", 443)
