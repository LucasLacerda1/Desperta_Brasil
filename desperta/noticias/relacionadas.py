"""
Decisao 25.13 (item 5): noticias relacionadas pelas fontes em comum.

Duas noticias publicadas sao relacionadas quando citam a mesma proposicao, votacao,
evento ou orgao em `noticia_fonte`. A votacao conta tambem as proposicoes que ela
afeta (`votacao.proposicao_id` e `votacao_proposicao`): a noticia da votacao de um
projeto e relacionada a noticia do projeto e ao boletim que cita outra votacao dele.
O orgao so reforca uma ligacao que ja existe: sozinho, ele ligaria toda votacao do
Plenario a todas as outras. Deputado e partido nao ligam noticias. Sem tabela
nova: tudo sai de `noticia_fonte` e das tabelas da API.
"""

from desperta.ext.db import db
from desperta.votacoes.models import Votacao, VotacaoProposicao

from .models import Noticia, NoticiaFonte

TIPOS_QUE_LIGAM = ("proposicao", "votacao", "evento", "orgao")
# Tipos que contam no desempate, mas nao ligam duas noticias sozinhos
TIPOS_SO_DE_REFORCO = ("orgao",)
LIMITE_RELACIONADAS = 5


def _proposicoes_das_votacoes(votacoes):
    """As proposicoes afetadas por cada votacao (objeto e votacao_proposicao)."""
    if not votacoes:
        return set()
    afetadas = db.session.scalars(
        db.select(VotacaoProposicao.proposicao_id).where(VotacaoProposicao.votacao_id.in_(votacoes))
    ).all()
    objetos = db.session.scalars(
        db.select(Votacao.proposicao_id).where(Votacao.id.in_(votacoes), Votacao.proposicao_id.is_not(None))
    ).all()
    return {str(p) for p in (*afetadas, *objetos)}


def _votacoes_das_proposicoes(proposicoes):
    """As votacoes que afetam alguma das proposicoes (o caminho de volta)."""
    if not proposicoes:
        return set()
    ids = [int(p) for p in proposicoes if p.isdigit()]
    afetam = db.session.scalars(
        db.select(VotacaoProposicao.votacao_id).where(VotacaoProposicao.proposicao_id.in_(ids))
    ).all()
    objeto = db.session.scalars(db.select(Votacao.id).where(Votacao.proposicao_id.in_(ids))).all()
    return set(afetam) | set(objeto)


def chaves_da_noticia(noticia):
    """
    As fontes que ligam esta noticia a outras, como pares (tipo, ref_id).
    Proposicao e votacao sao ampliadas pelos dois lados: as proposicoes que as
    votacoes da noticia afetam e as votacoes que afetam essas proposicoes.
    """
    chaves = {(f.tipo, f.ref_id) for f in noticia.fontes if f.tipo in TIPOS_QUE_LIGAM}
    votacoes = {ref for tipo, ref in chaves if tipo == "votacao"}
    proposicoes = {ref for tipo, ref in chaves if tipo == "proposicao"}
    proposicoes |= _proposicoes_das_votacoes(votacoes)
    votacoes |= _votacoes_das_proposicoes(proposicoes)
    chaves |= {("proposicao", p) for p in proposicoes}
    chaves |= {("votacao", v) for v in votacoes}
    return chaves


def relacionadas(noticia, limite=LIMITE_RELACIONADAS):
    """
    Ate `limite` noticias publicadas com fontes em comum (pelo menos uma que nao seja
    so de reforco), da que tem mais fontes em comum para a que tem menos; no empate,
    a publicada mais recentemente.
    """
    chaves = chaves_da_noticia(noticia)
    if not chaves:
        return []
    em_comum = db.func.count().label("em_comum")
    consulta = (
        db.select(Noticia, em_comum)
        .join(NoticiaFonte, NoticiaFonte.noticia_id == Noticia.id)
        .where(
            Noticia.status == "publicada",
            Noticia.id != noticia.id,
            db.tuple_(NoticiaFonte.tipo, NoticiaFonte.ref_id).in_(sorted(chaves)),
        )
        .group_by(Noticia.id)
        .having(db.func.sum(db.case((NoticiaFonte.tipo.in_(TIPOS_SO_DE_REFORCO), 0), else_=1)) > 0)
        .order_by(em_comum.desc(), Noticia.publicado_em.desc(), Noticia.id.desc())
        .limit(limite)
    )
    return [n for n, _ in db.session.execute(consulta).all()]
