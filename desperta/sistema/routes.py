from flask import Blueprint

from desperta.auth import sessao
from desperta.ext.api import pagina, paginado, parametro_int, parametro_texto

from . import services

bp = Blueprint("sistema", __name__)


@bp.get("/situacao")
def situacao():
    """RNF05 (publica): ultima coleta concluida e aviso de dados desatualizados."""
    return services.situacao_dos_dados()


@bp.get("/coletas")
@sessao.so_admin
def coletas():
    """?status= (ok, parcial, erro) e ?recurso= (proposicoes, votacoes...)."""
    pagina_atual, por_pagina = pagina()
    itens, total = services.listar_coletas(
        parametro_texto("status", 20), parametro_texto("recurso", 50), pagina_atual, por_pagina
    )
    return paginado([services.como_coleta(c) for c in itens], total, pagina_atual, por_pagina)


@bp.get("/log")
@sessao.so_admin
def log():
    """?nivel= (info, aviso, erro), ?modulo= (coletor, IA, admin) e ?coleta=."""
    pagina_atual, por_pagina = pagina()
    itens, total = services.listar_log(
        parametro_texto("nivel", 10), parametro_texto("modulo", 20), parametro_int("coleta"), pagina_atual, por_pagina
    )
    return paginado([services.como_log(r) for r in itens], total, pagina_atual, por_pagina)
