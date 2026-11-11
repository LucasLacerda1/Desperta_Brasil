from desperta.ext.api import iso, iso_camara, url_camara
from desperta.ext.db import db
from desperta.ext.erros import NaoEncontrado
from desperta.noticias.models import Noticia, NoticiaFonte
from desperta.votacoes.models import Votacao, VotacaoProposicao

from .models import Proposicao, ProposicaoTema, Tema, Tramitacao

# ----------------------------------------------------------
# Transparencia (05/11/2026): campo que a Camara nao informou aparece como tal no portal.
# O banco guarda o que a API mandou ("", "." ou nulo); aqui o codigo reconhece e explica.
# ----------------------------------------------------------
# A API usa "." no lugar do regime e da apreciacao quando nao ha informacao
VALORES_SEM_INFORMACAO = ("", ".", "-")
NAO_INFORMADO = "não informado pela Câmara"
NAO_INFORMADA = "não informada pela Câmara"


def informado(valor):
    """Devolve o valor sem espacos, ou None se a Camara nao informou."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return None if texto in VALORES_SEM_INFORMACAO else texto


def ou_nao_informado(valor, feminino=False):
    return informado(valor) or (NAO_INFORMADA if feminino else NAO_INFORMADO)


# ======================================================
# PORTAL: PAGINA DA PROPOSICAO (RF09)
# ======================================================
TRAMITACOES_NO_DETALHE = 20
URL_PAGINA = "https://www.camara.leg.br/propostas-legislativas/{}"


def sigla_completa(proposicao):
    return f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano}"


def buscar_proposicao(proposicao_id):
    proposicao = db.session.get(Proposicao, proposicao_id)
    if proposicao is None:
        raise NaoEncontrado("Proposicao nao encontrada.")
    return proposicao


def como_resumo(proposicao):
    return {"id": proposicao.id, "sigla": sigla_completa(proposicao), "ementa": proposicao.ementa}


def como_tramitacao(tramitacao):
    """Decisao 14.1: despacho vazio nao aparece, e orgao sem sigla mostra o nome."""
    orgao = informado(tramitacao.sigla_orgao) or (tramitacao.orgao.nome if tramitacao.orgao else None)
    return {
        "sequencia": tramitacao.sequencia,
        "data_hora": iso_camara(tramitacao.data_hora),
        "orgao": orgao,
        "descricao": tramitacao.descricao,
        "situacao": informado(tramitacao.situacao),
        "despacho": informado(tramitacao.despacho),
        "regime": ou_nao_informado(tramitacao.regime),
        "url": tramitacao.url,
    }


def listar_tramitacoes(proposicao_id, pagina=1, por_pagina=20):
    """Da mais recente para a mais antiga."""
    buscar_proposicao(proposicao_id)
    consulta = db.select(Tramitacao).filter_by(proposicao_id=proposicao_id)
    total = db.session.scalar(db.select(db.func.count()).select_from(consulta.subquery()))
    itens = db.session.scalars(
        consulta.order_by(Tramitacao.sequencia.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return itens, total


def como_dict(proposicao):
    """Pagina da proposicao: situacao (ou o que a Camara nao informou), autores, temas, andamento e votacoes."""
    recentes, total = listar_tramitacoes(proposicao.id, 1, TRAMITACOES_NO_DETALHE)
    votacoes = db.session.scalars(
        db.select(Votacao)
        .join(VotacaoProposicao, VotacaoProposicao.votacao_id == Votacao.id)
        .where(VotacaoProposicao.proposicao_id == proposicao.id)
        .order_by(Votacao.data_hora_registro.desc())
    ).all()
    noticias = db.session.scalars(
        db.select(Noticia)
        .join(NoticiaFonte, NoticiaFonte.noticia_id == Noticia.id)
        .where(NoticiaFonte.tipo == "proposicao", NoticiaFonte.ref_id == str(proposicao.id))
        .where(Noticia.status == "publicada")
        .order_by(Noticia.publicado_em.desc())
    ).all()
    return {
        "id": proposicao.id,
        "sigla": sigla_completa(proposicao),
        "tipo": proposicao.descricao_tipo,
        "ementa": proposicao.ementa,
        "ementa_detalhada": informado(proposicao.ementa_detalhada),
        "palavras_chave": informado(proposicao.keywords),
        "data_apresentacao": iso_camara(proposicao.data_apresentacao),
        "situacao": ou_nao_informado(proposicao.situacao, feminino=True),
        "data_situacao": iso_camara(proposicao.data_status),
        "regime": ou_nao_informado(proposicao.regime),
        "apreciacao": ou_nao_informado(proposicao.apreciacao, feminino=True),
        "url_inteiro_teor": informado(proposicao.url_inteiro_teor),
        "url_pagina": URL_PAGINA.format(proposicao.id),
        "url_dados_abertos": url_camara(f"proposicoes/{proposicao.id}"),
        "autores": [
            {"nome": a.nome, "tipo": a.tipo, "deputado_id": a.deputado_id, "proponente": a.proponente}
            for a in sorted(proposicao.autores, key=lambda a: a.ordem)
        ],
        "temas": [
            {"cod_tema": t.cod_tema, "nome": t.tema.nome, "icone": t.tema.icone, "relevancia": t.relevancia}
            for t in sorted(proposicao.temas, key=lambda t: -t.relevancia)
        ],
        "tramitacoes": {"itens": [como_tramitacao(t) for t in recentes], "total": total},
        "votacoes": [
            {
                "id": v.id,
                "data": iso_camara(v.data),
                "orgao": v.sigla_orgao,
                "descricao": v.descricao,
                "aprovacao": v.aprovacao,
            }
            for v in votacoes
        ],
        "noticias": [{"titulo": n.titulo, "slug": n.slug, "publicado_em": iso(n.publicado_em)} for n in noticias],
    }


# ======================================================
# TEMAS (categorias do portal, RF05)
# ======================================================
def listar_temas():
    """Todos os temas oficiais, com quantas noticias publicadas cada um tem."""
    publicadas = (
        db.select(Noticia.cod_tema, db.func.count().label("total"))
        .where(Noticia.status == "publicada")
        .group_by(Noticia.cod_tema)
        .subquery()
    )
    linhas = db.session.execute(
        db.select(Tema, db.func.coalesce(publicadas.c.total, 0))
        .outerjoin(publicadas, publicadas.c.cod_tema == Tema.cod_tema)
        .order_by(Tema.nome)
    ).all()
    return [
        {"cod_tema": tema.cod_tema, "nome": tema.nome, "icone": tema.icone, "noticias_publicadas": total}
        for tema, total in linhas
    ]


def proposicoes_do_tema(cod_tema):
    if db.session.get(Tema, cod_tema) is None:
        raise NaoEncontrado("Tema nao encontrado.")
    return db.session.scalar(db.select(db.func.count()).select_from(ProposicaoTema).filter_by(cod_tema=cod_tema))
