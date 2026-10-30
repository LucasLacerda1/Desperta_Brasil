from desperta.ext.db import db

from .models import Coleta


def ultima_coleta_concluida(recurso=None):
    """Data da ultima coleta com status ok (RNF05), geral ou de um recurso; None se nao houver."""
    consulta = db.select(db.func.max(Coleta.finalizado_em)).where(Coleta.status == "ok")
    if recurso is not None:
        consulta = consulta.where(Coleta.recurso == recurso)
    return db.session.scalar(consulta)
