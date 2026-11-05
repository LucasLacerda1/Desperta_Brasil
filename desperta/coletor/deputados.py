from desperta.ext.db import db
from desperta.parlamentares.models import Deputado, Partido

from .cliente import ErroAPI
from .execucao import Execucao
from .normalizacao import id_da_uri, opcional


def _valores(id_deputado, dados, sexo):
    # D3: partido_id so se o partido existe; sigla_partido sempre vem da API
    partido_id = id_da_uri(dados.get("uriPartido"), "partidos")
    if partido_id is not None and db.session.get(Partido, partido_id) is None:
        partido_id = None
    return {
        "id": id_deputado,
        "nome": dados.get("nome"),
        "sigla_uf": dados.get("siglaUf"),
        "sexo": sexo,
        "email": opcional(dados.get("email")),
        "url_foto": dados.get("urlFoto"),
        "id_legislatura": dados.get("idLegislatura"),
        "partido_id": partido_id,
        "sigla_partido": dados.get("siglaPartido"),
    }


def _manter_legislatura_mais_nova(registro, valores):
    """O mesmo id aparece em varias legislaturas: legislatura e partido so trocam pela mais nova."""
    if (valores.get("id_legislatura") or 0) < registro.id_legislatura:
        return {
            **valores,
            "id_legislatura": registro.id_legislatura,
            "partido_id": registro.partido_id,
            "sigla_partido": registro.sigla_partido,
        }
    return valores


def gravar_listagem(execucao, item, sexo):
    return execucao.principal(
        Deputado, item["id"], _valores(item["id"], item, sexo), ajustar=_manter_legislatura_mais_nova
    )


def gravar_detalhe(execucao, item):
    """Recebe o item de /deputados/{id}, usado quando o deputado nao veio na listagem."""
    valores = _valores(item["id"], item.get("ultimoStatus") or {}, item.get("sexo"))
    return execucao.principal(Deputado, item["id"], valores, ajustar=_manter_legislatura_mais_nova)


# Campos da listagem que vao para o banco: duas linhas do mesmo deputado so conflitam se um deles mudar
CAMPOS_DA_LISTAGEM = ("nome", "siglaUf", "email", "urlFoto", "idLegislatura", "uriPartido", "siglaPartido")


def _gravar_pagina_lida(execucao, cliente, itens, sexo):
    """
    A listagem por legislatura traz o mesmo deputado uma vez por partido em que ele esteve.
    Gravar as duas linhas trocava o partido a cada coleta; nesse caso vale o detalhe, com a situacao atual.
    """
    versoes = {}
    for item in itens:
        versoes.setdefault(item["id"], {})[tuple(item.get(campo) for campo in CAMPOS_DA_LISTAGEM)] = item
    for id_deputado, por_conteudo in versoes.items():
        if len(por_conteudo) == 1:
            gravar_listagem(execucao, next(iter(por_conteudo.values())), sexo)
        else:
            execucao.processar(
                "deputado",
                id_deputado,
                lambda id_deputado=id_deputado: gravar_detalhe(execucao, cliente.obter(f"deputados/{id_deputado}")),
            )
        execucao.concluir_item()


def coletar(cliente, id_legislatura):
    params = {"idLegislatura": id_legislatura}
    with Execucao(cliente, "deputados", "completa", "/deputados", params) as execucao:
        # A listagem nao traz o sexo: vem do filtro da chamada
        for sexo in ("M", "F"):
            itens = []
            try:
                for item in cliente.paginar("deputados", {**params, "siglaSexo": sexo, "itens": 100}):
                    itens.append(item)
            except ErroAPI as erro:
                # Um 504 no meio nao perde o que ja veio nem impede o outro filtro
                execucao.registrar_falha("deputado", f"siglaSexo={sexo}", erro)
                execucao.concluir_item()
            _gravar_pagina_lida(execucao, cliente, itens, sexo)
