from flask import Blueprint

from desperta.ext.api import pagina, paginado

from . import services

bp = Blueprint("proposicoes", __name__)


@bp.get("/temas")
def temas():
    """Os temas oficiais da Camara, que sao as categorias do portal."""
    return {"itens": services.listar_temas()}


@bp.get("/<int:proposicao_id>")
def detalhe(proposicao_id):
    """RF09: situacao, autores, temas, andamento (as 20 mais recentes) e votacoes."""
    return services.como_dict(services.buscar_proposicao(proposicao_id))


@bp.get("/<int:proposicao_id>/tramitacoes")
def tramitacoes(proposicao_id):
    """O andamento completo, em paginas, da mais recente para a mais antiga."""
    pagina_atual, por_pagina = pagina()
    itens, total = services.listar_tramitacoes(proposicao_id, pagina_atual, por_pagina)
    return paginado([services.como_tramitacao(t) for t in itens], total, pagina_atual, por_pagina)
