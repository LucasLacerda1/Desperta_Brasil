"""
Erros de regra de negocio que viram resposta HTTP com JSON (decisao 10.4).

Os services levantam estes erros; as rotas nao precisam tratar nada. Assim, um registro
em uso nunca vira erro 500: vira 409 com uma mensagem clara.
"""


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


def init_app(app):
    @app.errorhandler(ErroDoPortal)
    def _responder(erro):
        cabecalhos = {}
        if getattr(erro, "esperar_s", None):
            cabecalhos["Retry-After"] = str(erro.esperar_s)
        corpo = {"erro": erro.mensagem}
        if erro.campos:
            corpo["campos"] = erro.campos
        return corpo, erro.codigo, cabecalhos
