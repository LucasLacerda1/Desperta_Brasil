from datetime import datetime, timedelta, timezone

from flask import current_app

from desperta.ext.db import db
from desperta.orgaos.models import Evento, PautaItem
from desperta.proposicoes.models import Proposicao, Tramitacao
from desperta.votacoes.models import Votacao

TAMANHO_EMENTA_TRAMITACAO = 200


def _juntar(*partes):
    return " ".join(parte.strip() for parte in partes if parte and parte.strip())


def _proposicoes():
    colunas = (
        Proposicao.id,
        Proposicao.sigla_tipo,
        Proposicao.numero,
        Proposicao.ano,
        Proposicao.ementa,
        Proposicao.ementa_detalhada,
        Proposicao.keywords,
    )
    for id_, sigla, numero, ano, ementa, detalhada, keywords in db.session.execute(db.select(*colunas)).all():
        yield str(id_), _juntar(f"{sigla} {numero}/{ano}.", ementa, detalhada, keywords)


def _tramitacoes():
    """Decisao 16.3: so as recentes, comecando pela proposicao; um despacho sozinho nao diz de que projeto se trata."""
    dias = current_app.config["RAG_TRAMITACAO_DIAS"]
    corte = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=dias)
    consulta = (
        db.select(
            Tramitacao.proposicao_id,
            Tramitacao.sequencia,
            Tramitacao.data_hora,
            Tramitacao.sigla_orgao,
            Tramitacao.situacao,
            Tramitacao.despacho,
            Proposicao.sigla_tipo,
            Proposicao.numero,
            Proposicao.ano,
            Proposicao.ementa,
        )
        .join(Proposicao, Proposicao.id == Tramitacao.proposicao_id)
        .where(Tramitacao.data_hora >= corte)
    )
    for (
        proposicao_id,
        sequencia,
        data_hora,
        orgao,
        situacao,
        despacho,
        sigla,
        numero,
        ano,
        ementa,
    ) in db.session.execute(consulta).all():
        # Decisao 14.1: despacho vazio e "sem valor"; sem situacao, nao ha o que buscar
        if _juntar(situacao, despacho):
            yield f"{proposicao_id}/{sequencia}", _juntar(
                f"{sigla} {numero}/{ano} — {ementa[:TAMANHO_EMENTA_TRAMITACAO].strip()}",
                f"{data_hora:%d/%m/%Y}",
                f"{orgao}.",
                situacao,
                despacho,
            )


def _votacoes():
    colunas = (Votacao.id, Votacao.descricao, Votacao.sigla_orgao, Votacao.data, Votacao.aprovacao)
    for id_, descricao, orgao, data, aprovacao in db.session.execute(db.select(*colunas)).all():
        resultado = {True: "Resultado: aprovada.", False: "Resultado: rejeitada.", None: ""}[aprovacao]
        yield id_, _juntar(descricao, f"{orgao}, {data:%d/%m/%Y}.", resultado)


def _eventos():
    colunas = (Evento.id, Evento.descricao_tipo, Evento.descricao)
    for id_, descricao_tipo, descricao in db.session.execute(db.select(*colunas)).all():
        yield str(id_), _juntar(f"{descricao_tipo}.", descricao)


def _itens_de_pauta():
    colunas = (PautaItem.evento_id, PautaItem.ordem, PautaItem.topico, PautaItem.texto_parecer)
    for evento_id, ordem, topico, parecer in db.session.execute(db.select(*colunas)).all():
        if _juntar(topico, parecer):
            yield f"{evento_id}/{ordem}", _juntar(topico, parecer)


FONTES = {
    "proposicao": _proposicoes,
    "tramitacao": _tramitacoes,
    "votacao": _votacoes,
    "evento": _eventos,
    "pauta_item": _itens_de_pauta,
}


def textos_de_origem(tipos=None):
    """Devolve (tipo, ref_id, texto) de cada registro que vira trecho (secao 6.1)."""
    for tipo in tipos or FONTES:
        for ref_id, texto in FONTES[tipo]():
            yield tipo, ref_id, texto
