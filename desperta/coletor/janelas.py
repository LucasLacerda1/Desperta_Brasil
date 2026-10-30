from datetime import date, timedelta

from desperta.ext.db import db
from desperta.sistema.models import Coleta

JANELA_PADRAO_DIAS = 30
# Fevereiro a abril somam 89 dias: e o maior intervalo que nunca passa de 3 meses
DIAS_POR_JANELA = 89


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


def dividir_janela(inicio, fim):
    """
    /proposicoes e /votacoes recusam (HTTP 400) janelas maiores que 3 meses;
    /votacoes tambem exige dataInicio e dataFim no mesmo ano.
    """
    janelas = []
    while inicio <= fim:
        fim_janela = min(fim, inicio + timedelta(days=DIAS_POR_JANELA - 1), date(inicio.year, 12, 31))
        janelas.append((inicio, fim_janela))
        inicio = fim_janela + timedelta(days=1)
    return janelas
