"""
Erros de regra de negocio que viram resposta HTTP com JSON (decisao 10.4).

Tambem cuida do log da aplicacao e dos erros fora das regras: endereco que nao existe (404),
metodo errado (405) e erro inesperado (500) respondem em JSON nas rotas /api; o 500 fica
registrado no log com o metodo e o endereco, sem mostrar detalhes internos a quem chamou.

Os services levantam estes erros; as rotas nao precisam tratar nada. Assim, um registro
em uso nunca vira erro 500: vira 409 com uma mensagem clara.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import request
from werkzeug.exceptions import HTTPException


# === ErroDoPortal (base dos erros com codigo HTTP) ===
class ErroDoPortal(Exception):
    codigo = 400

    def __init__(self, mensagem, campos=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        # Formulario: {campo: mensagem}, para a tela mostrar o erro embaixo de cada campo
        self.campos = campos


# === DadosInvalidos (400: campo faltando, grande demais ou fora da lista) ===
class DadosInvalidos(ErroDoPortal):
    codigo = 400


# === NaoAutenticado (401: precisa entrar com e-mail e senha) ===
class NaoAutenticado(ErroDoPortal):
    codigo = 401


# === AcessoNegado (403: papel sem permissao) ===
class AcessoNegado(ErroDoPortal):
    codigo = 403


# === NaoEncontrado (404) ===
class NaoEncontrado(ErroDoPortal):
    codigo = 404


# === Conflito (409: registro em uso, duplicado ou que nao pode ser apagado) ===
class Conflito(ErroDoPortal):
    codigo = 409


# === MuitasTentativas (429: excesso de requisicoes, RNF10) ===
class MuitasTentativas(ErroDoPortal):
    codigo = 429

    def __init__(self, mensagem, esperar_s=None):
        super().__init__(mensagem)
        # Segundos ate poder tentar de novo: vira o cabecalho Retry-After
        self.esperar_s = esperar_s


# ======================================================
# FORMULARIOS (criterio de validacao no servidor)
# ======================================================
def conferir_formulario(validadores):
    """Confere todos os campos de uma vez, sem parar no primeiro erro.

    validadores: {campo: funcao sem argumento que devolve o valor limpo ou levanta DadosInvalidos}.
    Devolve {campo: valor limpo}; se algum campo falhar, levanta um DadosInvalidos com
    "campos" = {campo: mensagem}, que a API manda junto com o "erro".
    """
    valores, erros = {}, {}
    for campo, validar in validadores.items():
        try:
            valores[campo] = validar()
        except DadosInvalidos as erro:
            erros[campo] = erro.mensagem
    if erros:
        if len(erros) == 1:
            raise DadosInvalidos(next(iter(erros.values())), campos=erros)
        raise DadosInvalidos("Confira os campos marcados.", campos=erros)
    return valores


# Mensagens dos erros HTTP comuns, em portugues
MENSAGENS_HTTP = {
    400: "Requisicao invalida.",
    404: "Endereco nao encontrado na API.",
    405: "Metodo nao permitido neste endereco.",
    413: "O envio passa do tamanho permitido.",
}


def _configurar_log(app):
    """Nivel e formato do log; com LOG_ARQUIVO, grava tambem em arquivo (troca a cada 1 MB, guarda 5)."""
    nivel = getattr(logging, str(app.config.get("LOG_NIVEL", "INFO")).upper(), logging.INFO)
    app.logger.setLevel(nivel)
    arquivo = app.config.get("LOG_ARQUIVO")
    if arquivo and not app.testing:
        os.makedirs(os.path.dirname(os.path.abspath(arquivo)), exist_ok=True)
        manipulador = RotatingFileHandler(arquivo, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        manipulador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        manipulador.setLevel(nivel)
        app.logger.addHandler(manipulador)


def init_app(app):
    _configurar_log(app)

    @app.errorhandler(HTTPException)
    def _responder_http(erro):
        # Fora da API (nao ha paginas no Flask) fica a resposta padrao
        if not request.path.startswith("/api"):
            return erro
        mensagem = MENSAGENS_HTTP.get(erro.code, erro.description)
        return {"erro": mensagem}, erro.code

    @app.errorhandler(Exception)
    def _responder_inesperado(erro):
        # Registra tudo no log e responde sem detalhes internos; o banco desfaz o que ficou pela metade
        app.logger.exception("Erro inesperado em %s %s", request.method, request.path)
        try:
            from desperta.ext.db import db

            db.session.rollback()
        except Exception:  # noqa: BLE001 - o rollback nao pode esconder o erro original
            app.logger.warning("Nao foi possivel desfazer a sessao do banco depois do erro.")
        return {"erro": "Erro interno do servidor. O problema foi registrado no log."}, 500

    @app.errorhandler(ErroDoPortal)
    def _responder(erro):
        cabecalhos = {}
        if getattr(erro, "esperar_s", None):
            cabecalhos["Retry-After"] = str(erro.esperar_s)
        corpo = {"erro": erro.mensagem}
        if erro.campos:
            corpo["campos"] = erro.campos
        return corpo, erro.codigo, cabecalhos
