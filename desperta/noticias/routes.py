from flask import Blueprint

from desperta.auth import sessao
from desperta.ext.api import corpo_json, pagina, paginado, parametro_int, parametro_texto, periodo_em_utc

from . import services

bp = Blueprint("noticias", __name__)


# ======================================================
# PORTAL (sem login)
# ======================================================
@bp.get("")
def listar():
    """RF11: noticias publicadas, de todos os temas ou de um (?tema=)."""
    pagina_atual, por_pagina = pagina()
    itens, total = services.listar_publicadas(parametro_int("tema"), pagina_atual, por_pagina)
    return paginado([services.como_cartao(n) for n in itens], total, pagina_atual, por_pagina)


@bp.get("/principal")
def principal():
    """RF10: as principais de cada tema (?por_tema=, padrao 3)."""
    return {"secoes": services.pagina_principal(parametro_int("por_tema", 3, minimo=1, maximo=10))}


@bp.get("/busca")
def busca():
    """RF12: ?q= com ?dia=, ?mes= e ?ano= em horario de Brasilia, e ?tema=."""
    pagina_atual, por_pagina = pagina()
    inicio, fim = periodo_em_utc(
        parametro_int("dia", minimo=1, maximo=31), parametro_int("mes", minimo=1, maximo=12),
        parametro_int("ano", minimo=1900, maximo=2999),
    )
    itens, total = services.buscar_publicadas(
        parametro_texto("q"), inicio, fim, parametro_int("tema"), pagina_atual, por_pagina
    )
    return paginado([services.como_cartao(n) for n in itens], total, pagina_atual, por_pagina)


@bp.get("/<slug>")
def detalhe(slug):
    """RF18: a noticia pelo endereco proprio; cada abertura conta uma visualizacao."""
    noticia = services.publicada_pelo_slug(slug)
    services.contar_visualizacao(noticia)
    return services.como_completa(noticia)


# ======================================================
# AREA ADMINISTRATIVA (login da equipe)
# ======================================================
@bp.get("/admin")
@sessao.login_obrigatorio
def fila():
    """Fila da equipe: ?status=, ?tema=, ?caso= (votacao, situacao, nova) e ?origem= (ia, equipe)."""
    pagina_atual, por_pagina = pagina()
    itens, total = services.listar_para_revisao(
        parametro_texto("status", 20), parametro_int("tema"), parametro_texto("caso", 20),
        parametro_texto("origem", 20), pagina_atual, por_pagina,
    )
    return paginado([services.como_item_de_revisao(n) for n in itens], total, pagina_atual, por_pagina)


@bp.post("/admin")
@sessao.login_obrigatorio
def criar():
    dados = corpo_json()
    noticia = services.criar_pela_equipe(
        sessao.admin_atual(), dados.get("titulo"), dados.get("resumo"), dados.get("corpo"), dados.get("cod_tema"),
        dados.get("fontes"), dados.get("tipo", "noticia"),
    )
    return services.como_detalhe_de_revisao(noticia), 201


@bp.post("/admin/lote")
@sessao.login_obrigatorio
def lote():
    dados = corpo_json()
    feitas, falhas = services.mudar_status_em_lote(
        dados.get("ids"), sessao.admin_atual(), dados.get("acao"), dados.get("comentario")
    )
    return {"feitas": feitas, "falhas": falhas}


@bp.get("/admin/<int:noticia_id>")
@sessao.login_obrigatorio
def detalhe_para_revisao(noticia_id):
    return services.como_detalhe_de_revisao(services.buscar_para_revisao(noticia_id))


@bp.patch("/admin/<int:noticia_id>")
@sessao.login_obrigatorio
def editar(noticia_id):
    dados = corpo_json()
    noticia = services.buscar_para_revisao(noticia_id)
    campos = {c: dados[c] for c in ("titulo", "resumo", "corpo", "cod_tema") if c in dados}
    services.editar_noticia(noticia, sessao.admin_atual(), **campos)
    return services.como_detalhe_de_revisao(noticia)


@bp.post("/admin/<int:noticia_id>/<acao>")
@sessao.login_obrigatorio
def mudar_status(noticia_id, acao):
    """acao = aprovar, publicar, rejeitar (com comentario) ou arquivar."""
    dados = corpo_json(obrigatorio=False)
    noticia = services.buscar_para_revisao(noticia_id)
    services.mudar_status(noticia, sessao.admin_atual(), acao, dados.get("comentario"))
    return services.como_detalhe_de_revisao(noticia)


@bp.delete("/admin/<int:noticia_id>")
@sessao.so_admin
def excluir(noticia_id):
    """Decisao 10.4: so rascunho ou rejeitada, e so o admin; o normal e arquivar."""
    services.excluir_noticia(services.buscar_para_revisao(noticia_id), sessao.admin_atual())
    return "", 204
