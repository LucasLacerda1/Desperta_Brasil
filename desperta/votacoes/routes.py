from flask import Blueprint

from . import services

bp = Blueprint("votacoes", __name__)


@bp.get("/<votacao_id>")
def detalhe(votacao_id):
    """RF09: resultado, situacao dos votos, voto de cada deputado e orientacoes (id no formato 2310837-8)."""
    return services.como_dict(services.buscar_votacao(votacao_id))
