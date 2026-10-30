from datetime import date, timedelta

from desperta.ext.db import db
from desperta.sistema.models import Coleta

JANELA_PADRAO_DIAS = 30


def janela_incremental(recurso, hoje=None):
    """A proxima janela comeca na ultima janela ok do recurso, com 1 dia de sobreposicao."""
    hoje = hoje or date.today()
    ultimo_fim = db.session.scalar(
        db.select(Coleta.data_fim_ref)
        .where(Coleta.recurso == recurso, Coleta.status == "ok", Coleta.data_fim_ref.is_not(None))
        .order_by(Coleta.data_fim_ref.desc())
        .limit(1)
    )
    if ultimo_fim is None:
        return hoje - timedelta(days=JANELA_PADRAO_DIAS), hoje
    return min(ultimo_fim - timedelta(days=1), hoje), hoje


def dividir_por_ano(inicio, fim):
    """/votacoes exige dataInicio e dataFim no mesmo ano."""
    return [(max(inicio, date(ano, 1, 1)), min(fim, date(ano, 12, 31))) for ano in range(inicio.year, fim.year + 1)]
