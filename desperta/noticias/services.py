import re
import unicodedata
from datetime import datetime, timedelta

from desperta.ext.db import db

from .models import Noticia, NoticiaFonte

noticia_fts = db.table("noticia_fts", db.column("rowid"))

TAMANHO_SLUG = 220


def gerar_slug(titulo):
    """Sem acento, minusculo e unico; depois de publicada, a noticia nao muda de slug."""
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:TAMANHO_SLUG].rstrip("-") or "noticia"
    slug = base
    numero = 2
    while db.session.scalar(db.select(Noticia.id).filter_by(slug=slug).limit(1)) is not None:
        sufixo = f"-{numero}"
        slug = base[: TAMANHO_SLUG - len(sufixo)].rstrip("-") + sufixo
        numero += 1
    return slug


def criar_rascunho(titulo, resumo, corpo, cod_tema, fontes, origem="ia"):
    """RF06: toda noticia gerada entra como rascunho; fontes sao (tipo, ref_id), a primeira e a principal."""
    noticia = Noticia(
        titulo=titulo,
        slug=gerar_slug(titulo),
        resumo=resumo,
        corpo=corpo,
        origem=origem,
        cod_tema=cod_tema,
        status="rascunho",
    )
    db.session.add(noticia)
    db.session.flush()
    db.session.add_all(
        NoticiaFonte(noticia_id=noticia.id, tipo=tipo, ref_id=ref_id, ordem=ordem)
        for ordem, (tipo, ref_id) in enumerate(fontes, start=1)
    )
    return noticia


def _termo_para_match(termo):
    """Cada palavra vira uma frase entre aspas, para nao quebrar a sintaxe do MATCH."""
    palavras = (termo or "").split()
    return " ".join('"' + palavra.replace('"', '""') + '"' for palavra in palavras)


def buscar_noticias(termo, inicio=None, fim=None, cod_tema=None):
    """
    Busca nas noticias publicadas, por relevancia e depois pela mais recente.
    inicio e fim comparam com publicado_em (UTC); fim sem hora inclui o dia inteiro.
    """
    match = _termo_para_match(termo)
    if not match:
        return []

    consulta = (
        db.select(Noticia)
        .join(noticia_fts, noticia_fts.c.rowid == Noticia.id)
        .where(db.text("noticia_fts MATCH :termo").bindparams(termo=match))
        .where(Noticia.status == "publicada")
    )
    if inicio is not None:
        consulta = consulta.where(Noticia.publicado_em >= inicio)
    if fim is not None:
        if isinstance(fim, datetime):
            consulta = consulta.where(Noticia.publicado_em <= fim)
        else:
            consulta = consulta.where(Noticia.publicado_em < fim + timedelta(days=1))
    if cod_tema is not None:
        consulta = consulta.where(Noticia.cod_tema == cod_tema)

    consulta = consulta.order_by(db.func.bm25(db.literal_column("noticia_fts")), Noticia.publicado_em.desc())
    return list(db.session.scalars(consulta))
