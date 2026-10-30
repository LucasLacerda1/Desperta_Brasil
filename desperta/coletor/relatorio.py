import re
from collections import Counter

from desperta.ext.db import db
from desperta.sistema.models import Coleta, LogSistema

PADRAO_NOT_NULL = re.compile(r"NOT NULL constraint failed: (\w+\.\w+)")


def falhas_por_coluna():
    """Para a carga de validacao: colunas que falharam e quantas vezes (decisao 10.2)."""
    descricoes = db.session.execute(
        db.select(LogSistema.entidade, LogSistema.descricao).where(LogSistema.acao == "gravar_registro")
    )
    contagem = Counter()
    for entidade, descricao in descricoes:
        achado = PADRAO_NOT_NULL.search(descricao)
        contagem[achado.group(1) if achado else f"{entidade}: {descricao[:80]}"] += 1
    return contagem.most_common()


def resumo_por_recurso():
    """Requisicoes, erros HTTP e itens por recurso, em todas as coletas."""
    return db.session.execute(
        db.select(
            Coleta.recurso,
            db.func.count(),
            db.func.sum(Coleta.requisicoes),
            db.func.sum(Coleta.erros_http),
            db.func.sum(Coleta.total_itens),
            db.func.sum(Coleta.itens_novos),
        )
        .group_by(Coleta.recurso)
        .order_by(Coleta.recurso)
    ).all()
