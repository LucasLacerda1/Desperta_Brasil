from desperta.parlamentares.models import Partido

from .execucao import Execucao
from .normalizacao import opcional


def gravar_partido(execucao, item):
    """Recebe o item de /partidos/{id}, que traz urlLogo."""
    return execucao.principal(
        Partido,
        item["id"],
        {
            "id": item["id"],
            "sigla": item.get("sigla"),
            "nome": item.get("nome"),
            "url_logo": opcional(item.get("urlLogo")),
        },
    )


def coletar(cliente, id_legislatura):
    params = {"idLegislatura": id_legislatura, "itens": 100}
    with Execucao(cliente, "partidos", "completa", "/partidos", params) as execucao:
        for item in list(cliente.paginar("partidos", params)):
            execucao.processar(
                "partido",
                item["id"],
                lambda item=item: gravar_partido(execucao, cliente.obter(f"partidos/{item['id']}")),
            )
