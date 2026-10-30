"""Responde como a API da Camara, com arquivos JSON gravados; nenhum teste chama a API real."""

import json
from pathlib import Path

import requests

PASTA = Path(__file__).parent / "fixtures" / "camara"
URL_BASE = "https://api.falsa/api/v2"


def carregar(nome):
    return json.loads((PASTA / f"{nome}.json").read_text(encoding="utf-8"))


def envelope(dados, proxima=None):
    links = [{"rel": "self", "href": "x"}]
    if proxima:
        links.append({"rel": "next", "href": proxima})
    return {"dados": dados, "links": links}


class RespostaFalsa:
    def __init__(self, status_code, corpo=None):
        self.status_code = status_code
        self._corpo = corpo

    def json(self):
        if self._corpo is None:
            raise ValueError("sem JSON")
        return self._corpo


class ApiFalsa:
    """Implementa o get do requests.Session; rota sem resposta faz o teste falhar."""

    def __init__(self):
        self.rotas = {}
        self.chamadas = []

    def responder(self, caminho, corpo):
        """corpo: envelope, funcao(params), excecao, status int ou lista consumida a cada chamada."""
        self.rotas[caminho] = corpo

    def caminhos_chamados(self):
        return [caminho for caminho, _ in self.chamadas]

    def get(self, url, params=None, headers=None, timeout=None):
        assert timeout, "toda chamada precisa de timeout"
        caminho = url.split("/api/v2/", 1)[1]
        self.chamadas.append((caminho, params))
        corpo = self.rotas.get(caminho)
        if corpo is None:
            prefixo = caminho.rsplit("/", 1)[0] + "/*"
            corpo = self.rotas.get(prefixo)
            assert corpo is not None, f"Rota sem resposta no teste: {caminho}"
            if callable(corpo):
                corpo = corpo(caminho.rsplit("/", 1)[1])
        elif callable(corpo):
            corpo = corpo(params or {})
        if isinstance(corpo, list):
            corpo = corpo.pop(0)
        if isinstance(corpo, requests.RequestException):
            raise corpo
        if isinstance(corpo, int):
            return RespostaFalsa(corpo)
        return RespostaFalsa(200, corpo)
