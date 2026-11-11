"""
Erros de regra de negocio que viram resposta HTTP com JSON (decisao 10.4).

Os services levantam estes erros; as rotas nao precisam tratar nada. Assim, um registro
em uso nunca vira erro 500: vira 409 com uma mensagem clara.
"""


# === ErroDoPortal (base dos erros com codigo HTTP) ===
class ErroDoPortal(Exception):
    codigo = 400

    def __init__(self, mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem


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


def init_app(app):
    @app.errorhandler(ErroDoPortal)
    def _responder(erro):
        return {"erro": erro.mensagem}, erro.codigo
