import hashlib
from datetime import datetime, time

from desperta.ext.api import iso, iso_camara, url_camara
from desperta.ext.db import db
from desperta.ext.erros import NaoEncontrado
from desperta.noticias.models import Noticia, NoticiaFonte
from desperta.votacoes.models import Votacao, VotacaoProposicao

from .models import (
    TEMA_SEM_CLASSIFICACAO,
    TEMA_SEM_CLASSIFICACAO_ICONE,
    TEMA_SEM_CLASSIFICACAO_NOME,
    Proposicao,
    ProposicaoTema,
    Tema,
    Tramitacao,
)

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


# ----------------------------------------------------------
# A situacao mudou de verdade? (decisao 25.1)
# A Camara muda a data do status a cada passo do andamento, mesmo quando a situacao
# continua igual. So ha mudanca quando a Camara informa uma situacao e ela e diferente
# da ultima informada antes do dia do status.
# ----------------------------------------------------------
def situacao_mudou(proposicao_id, cod_situacao, data_status):
    if cod_situacao is None or data_status is None:
        # Sem situacao informada pela Camara nao ha mudanca de situacao para contar
        return False
    inicio_do_dia = datetime.combine(data_status.date(), time.min)
    anterior = db.session.scalar(
        db.select(Tramitacao.cod_situacao)
        .where(
            Tramitacao.proposicao_id == proposicao_id,
            Tramitacao.data_hora < inicio_do_dia,
            Tramitacao.cod_situacao.is_not(None),
        )
        .order_by(Tramitacao.data_hora.desc(), Tramitacao.sequencia.desc())
        .limit(1)
    )
    # Sem nenhuma anterior, esta e a primeira situacao que a Camara informa
    return anterior != cod_situacao


# ----------------------------------------------------------
# Tema principal (decisao 25.2)
# Na API, a relevancia e a posicao do tema na lista da Camara: 0 e o primeiro, o principal,
# e os seguintes vem com 1, 2, 3... A Camara ordena assim desde julho de 2026; proposicao
# mais antiga vem com todos os temas em 0, sem ordem.
# ----------------------------------------------------------
def _taxa_de_tema_principal():
    """
    Para cada tema, a parte das proposicoes ordenadas pela Camara em que ele e o principal.
    A suavizacao (+1 e +2) evita que um tema visto poucas vezes fique com 0% ou 100%.
    """
    ordenadas = db.select(ProposicaoTema.proposicao_id).where(ProposicaoTema.relevancia > 0)
    linhas = db.session.execute(
        db.select(
            ProposicaoTema.cod_tema,
            db.func.count(),
            db.func.sum(db.case((ProposicaoTema.relevancia == 0, 1), else_=0)),
        )
        .where(ProposicaoTema.proposicao_id.in_(ordenadas))
        .group_by(ProposicaoTema.cod_tema)
    ).all()
    return {cod_tema: (principal + 1) / (presente + 2) for cod_tema, presente, principal in linhas}


def tema_principal(proposicao_id):
    """
    O tema principal da proposicao, ou None se ela nao tem tema.
    Com a ordem da Camara, e o de relevancia 0. Sem ordem (todos em 0), vale o tema que a
    Camara mais costuma por em primeiro lugar nas proposicoes que ela ordena.
    """
    temas = db.session.execute(
        db.select(ProposicaoTema.cod_tema, ProposicaoTema.relevancia)
        .filter_by(proposicao_id=proposicao_id)
        .order_by(ProposicaoTema.relevancia, ProposicaoTema.cod_tema)
    ).all()
    if not temas:
        return None
    if len(temas) == 1 or temas[-1].relevancia > 0:
        return temas[0].cod_tema
    taxas = _taxa_de_tema_principal()
    # Tema que nunca apareceu numa proposicao ordenada fica no meio (0,5); empate, o menor codigo
    return max(temas, key=lambda tema: (taxas.get(tema.cod_tema, 0.5), -tema.cod_tema)).cod_tema


# ======================================================
# PORTAL: PAGINA DA PROPOSICAO (RF09)
# ======================================================
TRAMITACOES_NO_DETALHE = 20
URL_PAGINA = "https://www.camara.leg.br/propostas-legislativas/{}"


# ----------------------------------------------------------
# Proposicao sem tema da Camara (decisao 25.6)
# ----------------------------------------------------------
AVISO_SEM_TEMA = "A Câmara ainda não informou o tema desta proposição."
# Tema criado pelo portal: o hash marca a origem e passa na verificacao do banco (SHA-256)
HASH_DO_PORTAL = hashlib.sha256(b"tema criado pelo portal: sem tema informado pela Camara").hexdigest()


def tema_sem_classificacao():
    """O codigo do tema especial; cria a linha na primeira vez que for preciso."""
    if db.session.get(Tema, TEMA_SEM_CLASSIFICACAO) is None:
        db.session.add(
            Tema(
                cod_tema=TEMA_SEM_CLASSIFICACAO,
                nome=TEMA_SEM_CLASSIFICACAO_NOME,
                icone=TEMA_SEM_CLASSIFICACAO_ICONE,
                hash_origem=HASH_DO_PORTAL,
            )
        )
        db.session.flush()
    return TEMA_SEM_CLASSIFICACAO


def tema_da_noticia(proposicao_id):
    """(cod_tema, a Camara informou?): o tema principal, ou o tema especial quando nao ha nenhum."""
    cod_tema = tema_principal(proposicao_id)
    if cod_tema is None:
        return tema_sem_classificacao(), False
    return cod_tema, True


def sigla_completa(proposicao):
    return f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano}"


def buscar_proposicao(proposicao_id):
    proposicao = db.session.get(Proposicao, proposicao_id)
    if proposicao is None:
        raise NaoEncontrado("Proposicao nao encontrada.")
    return proposicao


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
    from desperta.sistema.lacunas import lacunas_da_proposicao

    from .situacoes import explicar_situacao

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
        # Decisao 25.13: o nome da Camara e a explicacao em linguagem popular
        "situacao_explicada": explicar_situacao(proposicao.cod_situacao, proposicao.situacao),
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
            # Relevancia 0 e o tema principal (25.2)
            for t in sorted(proposicao.temas, key=lambda t: (t.relevancia, t.cod_tema))
        ],
        # Transparencia (25.6): a falta de tema e dita, e nao so uma lista vazia
        "aviso_tema": None if proposicao.temas else AVISO_SEM_TEMA,
        # Decisao 25.13: o que a Camara nao informou, com prova (sem o nivel, que e interno)
        "lacunas": [lacuna.publica() for lacuna in lacunas_da_proposicao(proposicao)],
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
