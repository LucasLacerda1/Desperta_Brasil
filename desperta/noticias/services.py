from datetime import datetime, timedelta

from desperta.ext.db import db

from .models import Noticia

noticia_fts = db.table("noticia_fts", db.column("rowid"))


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
