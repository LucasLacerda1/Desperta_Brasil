import re
from collections import Counter, defaultdict

from flask import current_app

from desperta.ext.db import db
from desperta.proposicoes.models import Proposicao
from desperta.sistema.models import Coleta, LogSistema

PADRAO_NOT_NULL = re.compile(r"NOT NULL constraint failed: (\w+\.\w+)")
PADRAO_API = re.compile(r"/api/v2/(\w+).*?(HTTP \d+|JSON invalido)")
ACOES_DE_FALHA = ("gravar_registro", "falha_api")
TABELAS_DA_PROPOSICAO = ("proposicao", "proposicao_autor", "proposicao_tema", "tramitacao")


def _eh_falha_da_api(descricao):
    return "/api/v2/" in descricao


def falhas_por_coluna():
    """Para a carga de validacao: colunas que falharam e quantas vezes (decisao 10.2)."""
    descricoes = db.session.execute(
        db.select(LogSistema.entidade, LogSistema.descricao).where(LogSistema.acao == "gravar_registro")
    )
    contagem = Counter()
    for entidade, descricao in descricoes:
        if _eh_falha_da_api(descricao):
            continue
        achado = PADRAO_NOT_NULL.search(descricao)
        contagem[achado.group(1) if achado else f"{entidade}: {descricao[:80]}"] += 1
    return contagem.most_common()


def falhas_da_api():
    """Falhas que nao dizem nada sobre as colunas: a API nao respondeu, por endpoint e motivo."""
    descricoes = db.session.scalars(db.select(LogSistema.descricao).where(LogSistema.acao.in_(ACOES_DE_FALHA)))
    contagem = Counter()
    for descricao in descricoes:
        if _eh_falha_da_api(descricao):
            achado = PADRAO_API.search(descricao)
            contagem[f"/{achado.group(1)}: {achado.group(2)}" if achado else descricao[:80]] += 1
    return contagem.most_common()


def proposicoes_pendentes():
    """
    Decisao 13.5: proposicoes dos tipos acompanhados sem filhos, e quantas delas
    tiveram falha em mais de uma coleta. Uma falha repetida nao se resolve sozinha.
    """
    tipos = current_app.config["TIPOS_ACOMPANHADOS"]
    pendentes = set(
        db.session.scalars(
            db.select(Proposicao.id).where(
                Proposicao.filhos_sincronizados_em.is_(None), Proposicao.sigla_tipo.in_(tipos)
            )
        )
    )
    coletas_com_falha = defaultdict(set)
    falhas = db.session.execute(
        db.select(LogSistema.entidade_id, LogSistema.coleta_id).where(
            LogSistema.acao == "gravar_registro", LogSistema.entidade.in_(TABELAS_DA_PROPOSICAO)
        )
    )
    for entidade_id, coleta_id in falhas:
        # Nas tabelas filhas, o id e "proposicao/ordem"
        id_proposicao = (entidade_id or "").split("/")[0]
        if id_proposicao.isdigit():
            coletas_com_falha[int(id_proposicao)].add(coleta_id)
    repetidas = sum(1 for id_prop in pendentes if len(coletas_com_falha[id_prop]) > 1)
    return len(pendentes), repetidas


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


def blocos_com_id_errado():
    """Decisao 12.3: blocos com id errado em /blocos/{id}/partidos e siglas que nao ligaram."""
    return (
        db.session.scalar(
            db.select(db.func.count(LogSistema.entidade_id.distinct())).where(
                LogSistema.acao == "bloco_partido_id_errado"
            )
        ),
        db.session.scalar(db.select(db.func.count()).where(LogSistema.acao == "bloco_partido_sem_id")),
    )


def avisos_por_tipo():
    """Avisos do coletor, como referencia ausente e item de pauta repetido."""
    return db.session.execute(
        db.select(LogSistema.acao, db.func.count())
        .where(LogSistema.modulo == "coletor", LogSistema.nivel == "aviso")
        .group_by(LogSistema.acao)
        .order_by(db.func.count().desc())
    ).all()
