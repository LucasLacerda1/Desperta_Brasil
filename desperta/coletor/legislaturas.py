from datetime import date

from desperta.parlamentares.models import Legislatura

from .execucao import Execucao
from .normalizacao import para_data


def coletar(cliente):
    with Execucao(cliente, "legislaturas", "completa", "/legislaturas") as execucao:
        for item in list(cliente.paginar("legislaturas", {"itens": 100})):
            execucao.principal(
                Legislatura,
                item["id"],
                {
                    "id": item["id"],
                    "data_inicio": para_data(item.get("dataInicio")),
                    "data_fim": para_data(item.get("dataFim")),
                },
            )
        execucao.concluir_item()


def id_atual(cliente, hoje=None):
    dados = cliente.obter("legislaturas", {"data": (hoje or date.today()).isoformat()})
    return dados[0]["id"]
